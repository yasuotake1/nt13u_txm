# src/nt13u_txm/meas/maincontrol.py
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, cast

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader

from nt13u_txm._paths import get_latest_json_path
from nt13u_txm.meas.remoteexclient import CameraMode, DeviceBusyError, RemoteExClient


# ---------------------------
# Utilities
# ---------------------------

BUSY_STATE: int = 0
MEAS_SELF: bool = False

# ---- LIVE configuration (single source of truth) ----
LIVE_RING_SIZE = 10  # 0..9
_live_tmp_idx = -1

# These are set by MainControlWindow when LIVE starts.
LIVE_MODE: CameraMode = CameraMode.SingleAcquisition  # keep CameraMode enum
_latest_json = get_latest_json_path()
_tmp_dir = _latest_json.parent
_tmp_dir.mkdir(parents=True, exist_ok=True)


def next_tmp_path() -> Path:
    global _live_tmp_idx
    _live_tmp_idx = (_live_tmp_idx + 1) % LIVE_RING_SIZE
    return _tmp_dir / f"ImagingXAFS_tmp_{_live_tmp_idx:03d}.img"


def write_latest_json(img: Path) -> None:
    global _latest_json

    latest = {
        "path": str(img),
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "mode": LIVE_MODE.name,
    }

    tmp_path = _latest_json.with_suffix(_latest_json.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(latest, f, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, _latest_json)


# ---------------------------
# UI Loader
# ---------------------------

def load_ui(ui_path: Path, parent: Optional[QtWidgets.QWidget] = None) -> QtWidgets.QWidget:
    """
    Load a .ui file at runtime (no uic compile needed).
    """
    f = QFile(str(ui_path))
    if not f.open(QFile.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"Failed to open .ui: {ui_path}")
    try:
        loader = QUiLoader()
        w = loader.load(f, parent)
        if w is None:
            raise RuntimeError(f"QUiLoader failed to load UI: {ui_path}")
        return w
    finally:
        f.close()


# ---------------------------
# Startup worker (runs in QThread)
# ---------------------------

class StartupWorker(QtCore.QObject):
    sig_ok = QtCore.Signal()
    sig_error = QtCore.Signal(str)

    @QtCore.Slot()
    def run(self) -> None:
        try:
            c = RemoteExClient()
            c.connect()
            c.app_start(timeout_ms=60_000)
            c.disconnect()
            self.sig_ok.emit()
        except DeviceBusyError as e:
            self.sig_error.emit(f"Device busy at startup: {e}")
        except Exception as e:
            self.sig_error.emit(f"{type(e).__name__}: {e}")


# ---------------------------
# Live worker (runs in QThread)
# ---------------------------

class LiveWorker(QtCore.QObject):
    sig_status = QtCore.Signal(str)
    sig_error = QtCore.Signal(str)
    sig_stopped = QtCore.Signal()

    def __init__(self, exposure_ms_getter) -> None:
        super().__init__()
        self._exposure_ms_getter = exposure_ms_getter  # callable returning int
        self._stop = False

    @QtCore.Slot()
    def run(self) -> None:
        """LIVE ループ本体：接続→(必要なら露光更新)→Acq→Save→Delete→latest.json→繰り返し。"""
        self._stop = False

        try:
            client = RemoteExClient()
            client.connect()  # lock + TCP
            # AppStartは maincontrol 起動時に済ませる設計なので、ここでは通常呼ばない

            # 初期露光を反映
            exp_prev = int(self._exposure_ms_getter())
            client.set_single_acquisition(exp_prev)
            self.sig_status.emit(f"LIVE connected. exp={exp_prev} ms")

            while not self._stop:
                exp_now = int(self._exposure_ms_getter())
                if exp_now != exp_prev:
                    client.set_single_acquisition(exp_now)
                    exp_prev = exp_now
                    self.sig_status.emit(f"Exposure updated: {exp_prev} ms")

                # Acquire
                client.acq_and_wait()

                # Save/Delete/Show(=latest.json)
                img_path = next_tmp_path()
                client.save(str(img_path))
                client.delete()
                write_latest_json(img_path)

            self.sig_status.emit("LIVE stopping...")

        except DeviceBusyError as e:
            self.sig_error.emit(f"Device busy: {e}")
        except Exception as e:
            self.sig_error.emit(f"{type(e).__name__}: {e}")
        finally:
            try:
                if "client" in locals():
                    client.disconnect()
            except Exception:
                pass
            self.sig_stopped.emit()

    @QtCore.Slot()
    def request_stop(self) -> None:
        self._stop = True


# ---------------------------
# GUI
# ---------------------------

class MainControlWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        global BUSY_STATE, MEAS_SELF

        super().__init__()

        self.setWindowTitle("MainControl (LIVE only)")
        # ここも .ui 側に寄せたいなら削ってOK（ただしQMainWindowの初期サイズは結局ここで決まる）
        self.resize(520, 220)

        # --- UI: load .ui (top-level QWidget) and set as centralWidget ---
        ui_path = Path(__file__).with_name("maincontrol.ui")
        root = load_ui(ui_path, parent=self)
        self.setCentralWidget(root)
        self._ui_root = root  # centralWidget only disable/enable target

        # ---- bind widgets by objectName ----
        self.spin_exp = cast(QtWidgets.QSpinBox, root.findChild(QtWidgets.QSpinBox, "spin_exp"))
        self.btn_live = cast(QtWidgets.QPushButton, root.findChild(QtWidgets.QPushButton, "btn_live"))
        self.lbl_status = cast(QtWidgets.QLabel, root.findChild(QtWidgets.QLabel, "lbl_status"))

        missing = [name for name, w in [
            ("spin_exp", self.spin_exp),
            ("btn_live", self.btn_live),
            ("lbl_status", self.lbl_status),
        ] if w is None]
        if missing:
            raise RuntimeError(f"Missing widget(s) in UI (objectName mismatch): {missing}")

        # --- worker/thread state ---
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[LiveWorker] = None
        self._live_running = False

        # Signals
        self.btn_live.toggled.connect(self._on_live_toggled)

        # --- startup + polling state ---
        # 0: free, 1: LIVE, 2: self measuring (reserved), 3: external measuring
        BUSY_STATE = 0
        MEAS_SELF = False  # 今は未使用（将来ルーチン測定で True にする）
        self._probe_client = RemoteExClient()

        # 500ms polling timer (startup完了後に開始)
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll_500ms)

        # startup thread/worker/dialog
        self._startup_thread: Optional[QtCore.QThread] = None
        self._startup_worker: Optional[StartupWorker] = None
        self._startup_dialog: Optional[QtWidgets.QProgressDialog] = None

        # 起動中は centralWidget のみ無効化（startup完了後に有効化）
        self._ui_root.setEnabled(False)
        self._set_status("startup...")
        self._begin_startup()

    # ---------- status helper ----------

    @QtCore.Slot(str)
    def _set_status(self, text: str) -> None:
        # ここに将来ログウィンドウ、statusBar 等を足せる
        self.lbl_status.setText(text)

    def _exposure_ms(self) -> int:
        return int(self.spin_exp.value())

    # ---------- startup ----------

    def _begin_startup(self) -> None:
        # splash的ProgressDialog（キャンセルなし・無限進捗）
        dlg = QtWidgets.QProgressDialog("Starting camera (AppStart)...", "", 0, 0, self)
        dlg.setWindowTitle("Starting")
        dlg.setCancelButton(None)
        dlg.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.show()
        self._startup_dialog = dlg

        # ワーカーをQThreadで実行
        th = QtCore.QThread(self)
        wk = StartupWorker()
        wk.moveToThread(th)

        th.started.connect(wk.run)
        wk.sig_ok.connect(self._on_startup_ok)
        wk.sig_error.connect(self._on_startup_error)

        # 後始末
        wk.sig_ok.connect(th.quit)
        wk.sig_error.connect(th.quit)
        th.finished.connect(th.deleteLater)
        th.finished.connect(wk.deleteLater)

        self._startup_thread = th
        self._startup_worker = wk
        th.start()

    def _end_startup_dialog(self) -> None:
        if self._startup_dialog is not None:
            self._startup_dialog.hide()
            self._startup_dialog.deleteLater()
            self._startup_dialog = None
        self._startup_thread = None
        self._startup_worker = None

    def _on_startup_ok(self) -> None:
        self._end_startup_dialog()

        # startup完了 → UIを有効化
        self._ui_root.setEnabled(True)
        self._set_status("Ready.\n(camera initialized; sockets released)")

        # startup後のみポーリング開始
        self._poll_timer.start()
        self._poll_500ms()  # すぐ反映

    def _on_startup_error(self, msg: str) -> None:
        self._end_startup_dialog()

        # 失敗時はkill前提：UIは無効のまま
        self._set_status(f"ERROR: {msg}")
        self._ui_root.setEnabled(False)

    # ---------- polling ----------

    def _poll_500ms(self) -> None:
        global BUSY_STATE

        # 優先順位：LIVE > self measuring > external lock > free
        if self._live_running:
            new_state = 1
        elif MEAS_SELF:
            new_state = 2
        else:
            st = self._probe_client.get_lock_status()
            new_state = 3 if st.locked else 0

        if new_state != BUSY_STATE:
            BUSY_STATE = new_state
            self._apply_busy_state()

        # 将来：ここにエネルギー/ステージ等のポーリングを追加していく

    def _apply_busy_state(self) -> None:
        s = int(BUSY_STATE)

        if s == 0:
            # free
            self.spin_exp.setEnabled(True)
            self.btn_live.setEnabled(True)
            return

        if s == 1:
            # LIVE（停止できる必要があるのでボタンは有効）
            self.spin_exp.setEnabled(True)
            self.btn_live.setEnabled(True)
            return

        if s == 2:
            # self measuring（将来用）
            self.spin_exp.setEnabled(False)
            self.btn_live.setEnabled(False)
            return

        if s == 3:
            # external measuring：開始不可。もし万一ON中なら停止だけ許す。
            self.spin_exp.setEnabled(False)
            if self.btn_live.isChecked():
                self.btn_live.setEnabled(True)
            else:
                self.btn_live.setEnabled(False)
            return

    # -------- LIVE control --------

    def _on_live_toggled(self, checked: bool) -> None:
        if checked:
            self._start_live()
        else:
            self._stop_live()

    def _start_live(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        if self._live_running:
            return

        st = self._probe_client.get_lock_status()
        if st.locked:
            self._set_status(f"ERROR: Device busy (locked at {st.timestamp or 'unknown'})")
            if self.btn_live.isChecked():
                self.btn_live.blockSignals(True)
                try:
                    self.btn_live.setChecked(False)
                finally:
                    self.btn_live.blockSignals(False)
            return

        thread = QtCore.QThread(self)
        worker = LiveWorker(exposure_ms_getter=self._exposure_ms)
        worker.moveToThread(thread)

        # Wiring
        thread.started.connect(worker.run)
        worker.sig_status.connect(self._set_status)
        worker.sig_error.connect(self._on_live_error)
        worker.sig_stopped.connect(self._on_live_stopped)
        worker.sig_stopped.connect(thread.quit)
        worker.sig_stopped.connect(worker.deleteLater)

        def _on_thread_finished() -> None:
            self._live_running = False
            self._worker = None
            self._thread = None
            if not self.btn_live.isChecked() and self.btn_live.isEnabled():
                self._set_status("Ready. (LIVE stopped)")

        thread.finished.connect(_on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker

        # UI state
        self._live_running = True
        self.btn_live.setEnabled(True)
        self._set_status("LIVE starting...")

        thread.start()

    def _stop_live(self) -> None:
        if not self._live_running:
            return
        if self._worker is not None:
            QtCore.QTimer.singleShot(0, self._worker.request_stop)
        self._set_status("Stopping LIVE...")

        # NOTE: actual state reset happens in _on_live_stopped()

    def _on_live_error(self, msg: str) -> None:
        # Live worker reported error -> force button OFF
        self._set_status(f"ERROR: {msg}")
        if self.btn_live.isChecked():
            self.btn_live.blockSignals(True)
            try:
                self.btn_live.setChecked(False)
            finally:
                self.btn_live.blockSignals(False)

    def _on_live_stopped(self) -> None:
        if not self.btn_live.isChecked():
            return

        # ボタンがONのままstoppedが来るのは「例外停止」等なので、強制OFF
        self.btn_live.blockSignals(True)
        try:
            self.btn_live.setChecked(False)
        finally:
            self.btn_live.blockSignals(False)

    # -------- window close --------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        # LIVE中は閉じられない（あなたの要件）
        if self._live_running:
            QtWidgets.QMessageBox.information(self, "Busy", "LIVE is running. Stop LIVE before closing.")
            event.ignore()
            return

        # 終了時に AppEnd を送る（必要なら）
        try:
            c = RemoteExClient()
            c.connect()
            c.app_end(timeout_ms=20_000)
            c.disconnect()
        except Exception:
            pass

        event.accept()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    win = MainControlWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())