# src/nt13u_txm/view/viewlatest.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, cast

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

import nt13u_txm._paths as p


# ---------------------------
# ITEX .img loader (C# viewer 互換の読み)
# ---------------------------

def read_img_header(path: Path) -> tuple[int, int, int, int]:
    """
    Returns: (ofs, width, height, dep_code)
    - 先頭 64 bytes
    - 'I''M' チェック
    - ofs = UInt16 @2, wid @4, hei @6, dep @12
    - データ開始は 64 + ofs
    """
    with path.open("rb") as f:
        head = f.read(64)
        if len(head) < 64:
            raise ValueError(f"Header too short: {path}")
        if head[0] != ord("I") or head[1] != ord("M"):
            raise ValueError(f"Not ITEX .img (missing 'IM' signature): {path}")

        ofs = int.from_bytes(head[2:4], "little", signed=False)
        wid = int.from_bytes(head[4:6], "little", signed=False)
        hei = int.from_bytes(head[6:8], "little", signed=False)
        dep = int.from_bytes(head[12:14], "little", signed=False)

    return ofs, wid, hei, dep


def load_img_array(path: Path) -> np.ndarray:
    """
    dep_code:
      0 -> uint8
      2 -> uint16
      3 -> uint32
    Returns shape (H, W) row-major.
    """
    ofs, wid, hei, dep = read_img_header(path)

    if dep == 0:
        dtype = np.uint8
    elif dep == 2:
        dtype = np.uint16
    elif dep == 3:
        dtype = np.uint32
    else:
        raise ValueError(f"Unsupported bit-depth code: {dep} in {path}")

    data_offset = 64 + ofs
    count = wid * hei

    with path.open("rb") as f:
        f.seek(data_offset)
        arr = np.fromfile(f, dtype=dtype, count=count)

    if arr.size != count:
        raise ValueError(
            f"Unexpected EOF: got {arr.size} pixels, expected {count} ({hei}x{wid}) in {path}"
        )

    return arr.reshape((hei, wid))


# ---------------------------
# GUI
# ---------------------------

class ViewLatestWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        latest_json: Path,
        poll_ms: int,
        title: str,
        width: int,
        height: int,
        set_range_on_first_image: bool,
    ) -> None:
        super().__init__()

        self.setWindowTitle(title)
        self.resize(width, height)
        self.latest_json = latest_json
        self.poll_ms = poll_ms
        self.set_range_on_first_image = set_range_on_first_image

        # ---- layout ----
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        hbox = QtWidgets.QHBoxLayout(central)
        hbox.setContentsMargins(8, 8, 8, 8)
        hbox.setSpacing(8)

        # ---- left: pyqtgraph ----
        self.graphics = pg.GraphicsLayoutWidget()
        hbox.addWidget(self.graphics, stretch=1)

        # NOTE: Pylance対策で .ci 経由
        self.plot = self.graphics.ci.addPlot(row=0, col=0)
        vb = self.plot.getViewBox()
        vb.setAspectLocked(True)
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")

        self.img_item = pg.ImageItem(axisOrder="row-major")
        self.plot.addItem(self.img_item)

        # Histogram + LUT
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img_item)
        self.hist.gradient.loadPreset("grey")
        self.graphics.ci.addItem(self.hist, row=0, col=1)

        # ---- right panel ----
        panel = QtWidgets.QFrame()
        panel.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        panel.setFixedWidth(300)
        hbox.addWidget(panel, stretch=0)

        vbox = QtWidgets.QVBoxLayout(panel)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        self.lbl_info = QtWidgets.QLabel("starting...")
        self.lbl_info.setWordWrap(True)
        vbox.addWidget(self.lbl_info)

        self.chk_auto = QtWidgets.QCheckBox("Auto scale (min/max from image)")
        self.chk_auto.setChecked(True)
        vbox.addWidget(self.chk_auto)

        minmax_row = QtWidgets.QHBoxLayout()
        self.lbl_min = QtWidgets.QLabel("min: -")
        self.lbl_max = QtWidgets.QLabel("max: -")
        minmax_row.addWidget(self.lbl_min)
        minmax_row.addStretch(1)
        minmax_row.addWidget(self.lbl_max)
        vbox.addLayout(minmax_row)

        form = QtWidgets.QFormLayout()
        self.spin_min = QtWidgets.QDoubleSpinBox()
        self.spin_max = QtWidgets.QDoubleSpinBox()
        for sp in (self.spin_min, self.spin_max):
            sp.setDecimals(0)
            sp.setRange(0, 2**32 - 1)
            sp.setSingleStep(100)
        self.spin_min.setValue(0)
        self.spin_max.setValue(65535)
        form.addRow("Fixed min", self.spin_min)
        form.addRow("Fixed max", self.spin_max)
        vbox.addLayout(form)

        # cursor info (mouse-over)
        self.lbl_cursor = QtWidgets.QLabel("cursor: -")
        self.lbl_cursor.setWordWrap(True)
        vbox.addWidget(self.lbl_cursor)

        self.lbl_file = QtWidgets.QLabel("file: -")
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.lbl_file.setMinimumWidth(0)        
        vbox.addWidget(self.lbl_file)

        vbox.addStretch(1)

        # ---- internal state ----
        self._last_idx: Optional[int] = None
        self._last_path: Optional[str] = None
        self._ranged_once = False
        self._force_level_update = False

        # manualモード時に保持するlevels（hist/スピンどちらの操作でも更新される）
        self._manual_levels: tuple[float, float] = (float(self.spin_min.value()), float(self.spin_max.value()))

        # マウスオーバー表示用（元のdtypeのまま保持）
        self._last_arr_raw: Optional[np.ndarray] = None

        # UIシグナルのループ抑制
        self._in_programmatic_level_change = False

        # ---- wire signals ----
        self.chk_auto.toggled.connect(self._on_auto_toggled)
        self.spin_min.valueChanged.connect(self._on_spin_changed)
        self.spin_max.valueChanged.connect(self._on_spin_changed)
        self.hist.sigLevelsChanged.connect(self._on_hist_levels_changed)

        # mouse hover
        scene = cast(Any, self.graphics.scene())
        scene.sigMouseMoved.connect(self._on_mouse_moved)

        self._sync_scale_widgets()

        # ---- timer ----
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.poll_ms)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        QtCore.QTimer.singleShot(0, self.tick)

    # ---------- UI helpers ----------

    def _sync_scale_widgets(self) -> None:
        fixed = not self.chk_auto.isChecked()
        self.spin_min.setEnabled(fixed)
        self.spin_max.setEnabled(fixed)

    def _safe_set_levels(self, vmin: float, vmax: float) -> None:
        """Histogram/Imgのlevelsを一貫してセット（シグナルループを抑制）。"""
        if vmax <= vmin:
            vmax = vmin + 1.0
        self._in_programmatic_level_change = True
        try:
            self.hist.setLevels(vmin, vmax)
        finally:
            self._in_programmatic_level_change = False

    def _update_spinboxes_from_levels(self, vmin: float, vmax: float) -> None:
        """manual用の保持値とspinbox表示を同期。"""
        if vmax <= vmin:
            vmax = vmin + 1.0

        self._manual_levels = (float(vmin), float(vmax))

        self.spin_min.blockSignals(True)
        self.spin_max.blockSignals(True)
        try:
            self.spin_min.setValue(vmin)
            self.spin_max.setValue(vmax)
        finally:
            self.spin_min.blockSignals(False)
            self.spin_max.blockSignals(False)

    # ---------- Signal handlers ----------

    def _on_auto_toggled(self, checked: bool) -> None:
        self._sync_scale_widgets()
        # Auto OFFになった瞬間は「直前の手動レンジ」を適用して保持する。
        # Auto ONになった瞬間は、次のtickで自動追随。

        if checked:
            # 次のtickでmin/max再計算させる
            self._force_level_update = True
            return

        self._force_level_update = False
        vmin, vmax = self._manual_levels
        self._safe_set_levels(vmin, vmax)
        self.lbl_min.setText(f"min: {vmin:.0f}")
        self.lbl_max.setText(f"max: {vmax:.0f}")

    def _on_spin_changed(self, _value: float) -> None:
        if self.chk_auto.isChecked():
            return  # Auto中はspinは無効（UI上もdisable）
        vmin = float(self.spin_min.value())
        vmax = float(self.spin_max.value())
        self._update_spinboxes_from_levels(vmin, vmax)
        self._safe_set_levels(vmin, vmax)
        self.lbl_min.setText(f"min: {vmin:.0f}")
        self.lbl_max.setText(f"max: {vmax:.0f}")

    def _on_hist_levels_changed(self) -> None:
        if self._in_programmatic_level_change:
            return
        # ユーザーがヒストグラムスライダーを触ったら、それを「手動レンジ」として保持。
        levels = cast(tuple[float, float], self.hist.getLevels())
        vmin = float(levels[0])
        vmax = float(levels[1])

        self._update_spinboxes_from_levels(vmin, vmax)
        self.lbl_min.setText(f"min: {vmin:.0f}")
        self.lbl_max.setText(f"max: {vmax:.0f}")

        # Auto中にユーザー操作が入った = 明確に手動操作なので Auto を外す
        if self.chk_auto.isChecked():
            self.chk_auto.setChecked(False)

    def _on_mouse_moved(self, pos) -> None:
        arr = self._last_arr_raw
        if arr is None:
            return

        vb = self.plot.getViewBox()
        p = vb.mapSceneToView(pos)

        x = int(p.x())
        y = int(p.y())

        h, w = arr.shape
        if 0 <= x < w and 0 <= y < h:
            val = int(arr[y, x])
            self.lbl_cursor.setText(f"x={x}, y={y}, value={val}")
        else:
            self.lbl_cursor.setText("cursor: -")

    # ---------- Main loop ----------

    def tick(self) -> None:
        if not self.latest_json.exists():
            self.lbl_info.setText(f"latest.json not found: {self.latest_json}")
            return

        try:
            info = json.loads(self.latest_json.read_text(encoding="utf-8"))
            path = str(info["path"])
            idx = int(info.get("idx", -1))
            ts = str(info.get("timestamp", ""))
            mode = str(info.get("mode", ""))

            # 更新判定：新しいidx（またはpath）なら読み直す
            needs_reload = (self._last_idx != idx) or (self._last_path != path)
            if not needs_reload and not self._force_level_update:
                return

            img_path = Path(path)
            self.lbl_info.setText(f"load idx={idx} mode={mode} timestamp={ts}")
            self.lbl_file.setText(f"file: " + str(img_path).replace("\\", "\\" + "\u200b").replace("/", "/" + "\u200b"))

            arr_u = load_img_array(img_path)
            self._last_arr_raw = arr_u  # 元の値表示用に保持
            arr = arr_u.astype(np.float32, copy=False)

            # 画像更新（ズーム/パン保持のため setRange は基本触らない）
            self.img_item.setImage(arr, autoLevels=False)

            # 初回だけ全体表示（以後は保持）
            if self.set_range_on_first_image and (not self._ranged_once):
                h, w = arr.shape
                self.plot.getViewBox().setRange(xRange=(0, w), yRange=(0, h), padding=0.0)
                self._ranged_once = True

            # コントラスト更新
            if self.chk_auto.isChecked():
                vmin = float(np.min(arr))
                vmax = float(np.max(arr))
                self.lbl_min.setText(f"min: {vmin:.0f}")
                self.lbl_max.setText(f"max: {vmax:.0f}")
                self._safe_set_levels(vmin, vmax)
                self._force_level_update = False
            else:
                # manual: 現在保持しているレンジを適用（新画像でも保持）
                vmin, vmax = self._manual_levels
                self.lbl_min.setText(f"min: {vmin:.0f}")
                self.lbl_max.setText(f"max: {vmax:.0f}")
                self._safe_set_levels(vmin, vmax)

            self._last_idx = idx
            self._last_path = path

        except Exception as e:
            self.lbl_info.setText(f"ERROR: {type(e).__name__}: {e}")


def main() -> int:
    latest_json = p.get_latest_json_path()
    poll_ms = p.get_view_poll_ms()
    title = "ViewLatest (.img)"
    width = p.get_view_width()
    height = p.get_view_height()
    set_range_on_first_image = True

    pg.setConfigOptions(imageAxisOrder="row-major")

    app = QtWidgets.QApplication(sys.argv)
    win = ViewLatestWindow(latest_json, poll_ms, title, width, height, set_range_on_first_image)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
