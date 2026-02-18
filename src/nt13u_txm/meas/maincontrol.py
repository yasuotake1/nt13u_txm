# src/nt13u_txm/meas/maincontrol.py
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from pyqtgraph.Qt import QtCore, QtWidgets

import nt13u_txm._paths as p
from nt13u_txm.meas.remoteexclient import CameraMode, DeviceBusyError, RemoteExClient


# ---------------------------
# Utilities
# ---------------------------

@dataclass
class LiveConfig:
    tmp_dir: Path
    latest_json: Path
    mode: CameraMode = CameraMode.SingleAcquisition
    ring_size: int = 10  # 0..9


class TempPathCycler:
    """C# の idxTmp = idxTmp < 9 ? idxTmp + 1 : 0 を Python 化（リングバッファ）。"""

    def __init__(self, tmp_dir: Path, ring_size: int = 10) -> None:
        self._tmp_dir = tmp_dir
        self._ring_size = ring_size
        self._idx = 0

    @property
    def idx(self) -> int:
        return self._idx

    def next_path(self) -> Path:
        self._idx = (self._idx + 1) % self._ring_size
        return self._tmp_dir / f"ImagingXAFS_tmp_{self._idx:03d}.img"


def write_latest_json(latest_json: Path, img: Path, idx: int, mode: CameraMode) -> None:
    latest = {
        "path": str(img),
        "idx": int(idx),
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "mode": mode.name,
    }
    latest_json.parent.mkdir(parents=True, exist_ok=True)
    latest_json.write_text(json.dumps(latest, ensure_ascii=False), encoding="utf-8")


# ---------------------------
# Live worker (runs in QThread)
# ---------------------------

class LiveWorker(QtCore.QObject):
    sig_status = QtCore.Signal(str)
    sig_error = QtCore.Signal(str)
    sig_stopped = QtCore.Signal()

    def __init__(self, cfg: LiveConfig, exposure_ms_getter) -> None:
        super().__init__()
        self._cfg = cfg
        self._exposure_ms_getter = exposure_ms_getter  # callable returning int
        self._stop = False

    @QtCore.Slot()
    def run(self) -> None:
        """LIVE ループ本体：接続→(必要なら露光更新)→Acq→Save→Delete→latest.json→繰り返し。"""
        self._stop = False

        # Ensure directories exist
        self._cfg.tmp_dir.mkdir(parents=True, exist_ok=True)

        cycler = TempPathCycler(self._cfg.tmp_dir, ring_size=self._cfg.ring_size)

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
                img_path = cycler.next_path()
                client.save(str(img_path))
                client.delete()
                write_latest_json(self._cfg.latest_json, img_path, cycler.idx, self._cfg.mode)

            self.sig_status.emit("LIVE stopping...")

        except DeviceBusyError as e:
            self.sig_error.emit(f"Device busy: {e}")
        except Exception as e:
            self.sig_error.emit(f"{type(e).__name__}: {e}")
        finally:
            try:
                # Disconnect releases lock
                if "client" in locals():
                    client.disconnect()
            except Exception:
                pass
            self.sig_stopped.emit()

    def request_stop(self) -> None:
        self._stop = True


# ---------------------------
# GUI
# ---------------------------

class MainControlWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("MainControl (LIVE only)")
        self.resize(520, 220)

        # Paths
        self._tmp_dir = p.get_tmp_dir()
        self._latest_json = self._tmp_dir / "latest.json"

        # --- UI ---
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        self.spin_exp = QtWidgets.QSpinBox()
        self.spin_exp.setRange(1, 600_000)  # 1 ms .. 10 min
        self.spin_exp.setSingleStep(1)
        self.spin_exp.setValue(100)
        self.spin_exp.setSuffix(" ms")
        form.addRow("Exposure", self.spin_exp)

        self.btn_live = QtWidgets.QPushButton("LIVE")
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(False)
        self.btn_live.setMinimumHeight(36)
        layout.addWidget(self.btn_live)

        self.lbl_status = QtWidgets.QLabel("startup...")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        layout.addStretch(1)

        # --- worker/thread state ---
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[LiveWorker] = None
        self._live_running = False

        # Signals
        self.btn_live.toggled.connect(self._on_live_toggled)

        # Startup: pre-warm camera by AppStart once, then disconnect
        self._startup_camera()

    def _exposure_ms(self) -> int:
        return int(self.spin_exp.value())

    def _startup_camera(self) -> None:
        """
        起動時に AppStart(0) だけ実行して切断（あなたの確認した挙動を利用）。
        - ここで lock が取れない = 既に誰かが LIVE/測定中 → 起動失敗が妥当
        """
        self.lbl_status.setText("Connecting (AppStart)...")
        QtWidgets.QApplication.processEvents()

        try:
            c = RemoteExClient()
            c.connect()
            c.app_start(timeout_ms=60_000)
            c.disconnect()
            self.lbl_status.setText("Ready. (camera initialized; sockets released)")
        except DeviceBusyError as e:
            self.lbl_status.setText(f"ERROR: Device busy at startup: {e}")
            # 起動継続しても何もできないので、ボタンを無効化
            self.btn_live.setEnabled(False)
        except Exception as e:
            self.lbl_status.setText(f"ERROR: Startup failed: {type(e).__name__}: {e}")
            self.btn_live.setEnabled(False)

    # -------- LIVE control --------

    def _on_live_toggled(self, checked: bool) -> None:
        if checked:
            self._start_live()
        else:
            self._stop_live()

    def _start_live(self) -> None:
        if self._live_running:
            return

        cfg = LiveConfig(
            tmp_dir=self._tmp_dir,
            latest_json=self._latest_json,
            mode=CameraMode.SingleAcquisition,
            ring_size=10,
        )

        self._thread = QtCore.QThread(self)
        self._worker = LiveWorker(cfg, exposure_ms_getter=self._exposure_ms)
        self._worker.moveToThread(self._thread)

        # Wiring
        self._thread.started.connect(self._worker.run)
        self._worker.sig_status.connect(self.lbl_status.setText)
        self._worker.sig_error.connect(self._on_live_error)
        self._worker.sig_stopped.connect(self._on_live_stopped)

        # Cleanup
        self._worker.sig_stopped.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        # UI state
        self._live_running = True
        self.btn_live.setEnabled(True)
        self.lbl_status.setText("LIVE starting...")

        self._thread.start()

    def _stop_live(self) -> None:
        if not self._live_running:
            return
        if self._worker is not None:
            self._worker.request_stop()
        self.lbl_status.setText("Stopping LIVE...")

        # NOTE: actual state reset happens in _on_live_stopped()

    def _on_live_error(self, msg: str) -> None:
        # Live worker reported error -> force button OFF
        self.lbl_status.setText(f"ERROR: {msg}")
        if self.btn_live.isChecked():
            self.btn_live.blockSignals(True)
            try:
                self.btn_live.setChecked(False)
            finally:
                self.btn_live.blockSignals(False)

    def _on_live_stopped(self) -> None:
        self._live_running = False

        # worker/thread objects will be deleted via Qt parent or deleteLater
        self._worker = None
        self._thread = None

        if not self.btn_live.isChecked():
            # if user turned it off normally
            if not self.btn_live.isEnabled():
                return
            self.lbl_status.setText("Ready. (LIVE stopped)")

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
            # 終了動作なので握りつぶす（ログに出したければここで print）
            pass

        event.accept()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    win = MainControlWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
