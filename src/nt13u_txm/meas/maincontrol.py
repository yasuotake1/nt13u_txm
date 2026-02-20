# src/nt13u_txm/meas/maincontrol.py
from __future__ import annotations

import json
import os, sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pyqtgraph.Qt import QtCore, QtWidgets

from nt13u_txm._paths import get_latest_json_path
from nt13u_txm.meas.remoteexclient import CameraMode, DeviceBusyError, RemoteExClient


# ---------------------------
# Utilities
# ---------------------------

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
                # Disconnect releases lock
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
        super().__init__()

        self.setWindowTitle("MainControl (LIVE only)")
        self.resize(520, 220)

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
        self.spin_exp.setValue(1000)
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
        if self._thread is not None and self._thread.isRunning():
            return
        if self._live_running:
            return
        
        thread = QtCore.QThread(self)
        worker = LiveWorker(exposure_ms_getter=self._exposure_ms)
        worker.moveToThread(thread)

        # Wiring
        thread.started.connect(worker.run)
        worker.sig_status.connect(self.lbl_status.setText)
        worker.sig_error.connect(self._on_live_error)
        worker.sig_stopped.connect(self._on_live_stopped)
        worker.sig_stopped.connect(thread.quit)
        worker.sig_stopped.connect(worker.deleteLater)

        def _on_thread_finished() -> None:
            self._live_running = False
            self._worker = None
            self._thread = None
            if not self.btn_live.isChecked() and self.btn_live.isEnabled():
                self.lbl_status.setText("Ready. (LIVE stopped)")

        thread.finished.connect(_on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker

        # UI state
        self._live_running = True
        self.btn_live.setEnabled(True)
        self.lbl_status.setText("LIVE starting...")

        thread.start()


    def _stop_live(self) -> None:
        if not self._live_running:
            return
        if self._worker is not None:
            QtCore.QTimer.singleShot(0, self._worker.request_stop)
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
