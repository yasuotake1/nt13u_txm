# src/nt13u_txm/meas/remoteexclient.py
from __future__ import annotations

import locale
import socket
import time
from enum import Enum, auto
from pathlib import Path
from typing import Any, List, Optional

# Windows file locking
import msvcrt

import nt13u_txm._paths as paths


class DeviceBusyError(RuntimeError):
    """RemoteEx is locked by another process (e.g., LIVE is running elsewhere)."""


class CameraMode(Enum):
    SingleAcquisition = auto()
    AnalogIntegration = auto()
    Sequence = auto()


class _FileLockWin:
    """
    Minimal Windows non-blocking file lock based on msvcrt.locking.

    - lock is released automatically when the file handle is closed
    - we lock 1 byte from current file position (seek to 0)
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # "a+" keeps file if exists, creates if not
        fh = self._path.open("a+")
        try:
            fh.seek(0)
            # Lock 1 byte, non-blocking
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            fh.close()
            raise DeviceBusyError(f"RemoteEx is already in use (lock: {self._path}).") from e
        self._fh = fh

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            try:
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                # If unlock fails (rare), still close handle to let OS clean up.
                pass
        finally:
            try:
                self._fh.close()
            finally:
                self._fh = None

    @staticmethod
    def probe_locked(path: Path) -> bool:
        """
        Best-effort check: try acquiring lock and release immediately.
        True if locked by someone else.
        """
        lock = _FileLockWin(path)
        try:
            lock.acquire()
            return False
        except DeviceBusyError:
            return True
        finally:
            lock.release()


class RemoteExClient:
    """
    RemoteEx client with:
      - explicit connect()/disconnect()
      - AppStart/AppEnd split already in place
      - OS file lock (logs/remoteex.lock) acquired only while connected

    Intended usage:
      - maincontrol (LIVE ON): connect -> (optional app_start) -> loop -> disconnect
      - measurement script: connect -> do -> disconnect
    """

    def __init__(
        self,
        host_cmd: str = "127.0.0.1",
        port_cmd: int = 1001,
        host_data: str = "127.0.0.1",
        port_data: int = 1002,
        connect_timeout: float = 5.0,
        encoding: Optional[str] = None,
        lock_path: Optional[Path] = None,
    ) -> None:
        # store connection params only (no socket connect here)
        self._host_cmd = host_cmd
        self._port_cmd = port_cmd
        self._host_data = host_data
        self._port_data = port_data
        self._connect_timeout = float(connect_timeout)
        self._encoding = encoding or (locale.getpreferredencoding(False) or "utf-8")

        # lock file under logs/
        if lock_path is None:
            logs = paths.get_logs_dir()
            logs.mkdir(parents=True, exist_ok=True)
            lock_path = logs / "remoteex.lock"
        self._lock_path = lock_path
        self._lock = _FileLockWin(self._lock_path)

        # sockets are created in connect()
        self._sock_cmd: Optional[socket.socket] = None
        self._sock_data: Optional[socket.socket] = None
        self._rxbuf = bytearray()

        # Local state mirrors (client-side)
        self.exposure_time: int = 20
        self.num_exposures: int = 1
        self.mode: CameraMode = CameraMode.SingleAcquisition

    # -------------------------
    # Lock probe (for UI)
    # -------------------------

    def is_locked(self) -> bool:
        """Best-effort: True if another process holds RemoteEx lock."""
        return _FileLockWin.probe_locked(self._lock_path)

    # -------------------------
    # Connection lifecycle
    # -------------------------

    def connect(self) -> None:
        """
        Acquire file lock and open TCP connections.
        Raises DeviceBusyError if locked elsewhere.
        """
        if self.is_connected:
            return

        # 1) Acquire exclusive lock first (the "truth")
        self._lock.acquire()

        # 2) Then connect sockets
        try:
            self._sock_cmd = socket.create_connection(
                (self._host_cmd, self._port_cmd), timeout=self._connect_timeout
            )
            self._sock_data = socket.create_connection(
                (self._host_data, self._port_data), timeout=self._connect_timeout
            )
            self._rxbuf = bytearray()
            self._drain_greetings(timeout_s=0.3)
        except Exception as e:
            # if connection fails, release lock too
            self._safe_close_sockets()
            self._lock.release()
            raise RuntimeError("Connection failed: HiPic RemoteEx.") from e

    def disconnect(self) -> None:
        """Close TCP connections and release file lock."""
        self._safe_close_sockets()
        self._lock.release()

    @property
    def is_connected(self) -> bool:
        return self._sock_cmd is not None and self._sock_data is not None

    def _safe_close_sockets(self) -> None:
        for s in (self._sock_cmd, self._sock_data):
            if s is None:
                continue
            try:
                s.close()
            except Exception:
                pass
        self._sock_cmd = None
        self._sock_data = None

    # -------------------------
    # App lifecycle
    # -------------------------

    def app_start(self, timeout_ms: int = 60000) -> None:
        """
        Start RemoteEx application and connect to camera (can be slow).
        NOTE: You must be connected (connect()) before calling this.
        """
        self._ensure_connected()
        self.send_and_wait("AppStart(0)", recv_code=0, timeout_ms=timeout_ms)

    def app_end(self, timeout_ms: int = 20000) -> None:
        """
        End RemoteEx application (may release camera connection).
        NOTE: You must be connected (connect()) before calling this.
        """
        self._ensure_connected()
        self.send_and_wait("AppEnd()", recv_code=0, timeout_ms=timeout_ms)

    # -------------------------
    # Low-level comm
    # -------------------------

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError("RemoteExClient is not connected. Call connect() first.")

    def send(self, message: str) -> None:
        self._ensure_connected()
        assert self._sock_cmd is not None
        payload = (message + "\r").encode(self._encoding, errors="replace")
        self._sock_cmd.sendall(payload)

    def recv(self, timeout_ms: int = 10000) -> List[str]:
        self._ensure_connected()
        assert self._sock_cmd is not None

        deadline = time.time() + timeout_ms / 1000.0
        frames: List[str] = []

        def flush() -> None:
            while True:
                i = self._rxbuf.find(b"\r")
                if i < 0:
                    return
                raw = bytes(self._rxbuf[:i])
                del self._rxbuf[:i + 1]
                if raw == b"":
                    continue
                frames.append(raw.decode(self._encoding, errors="replace"))

        flush()
        if frames:
            return frames

        self._sock_cmd.settimeout(0.2)
        try:
            while time.time() < deadline:
                try:
                    chunk = self._sock_cmd.recv(4096)
                except socket.timeout:
                    flush()
                    if frames:
                        return frames
                    continue

                if not chunk:
                    break
                self._rxbuf.extend(chunk)
                flush()
                if frames:
                    return frames
        finally:
            self._sock_cmd.settimeout(None)

        return frames

    def send_and_wait(self, send_message: str, recv_code: int = 0, timeout_ms: int = 10000) -> None:
        self.send(send_message)

        func = send_message.split("(", 1)[0]
        target_prefix = f"{recv_code},{func}".lower()

        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            remaining = int(max(1, (deadline - time.time()) * 1000))
            for line in self.recv(timeout_ms=remaining):
                low = line.lower()

                # greetings etc.
                if low.startswith("remoteex "):
                    continue

                # Message / MsgBoxReply
                if low.startswith("4,") or low.startswith("5,"):
                    continue

                if low.startswith(target_prefix):
                    return

        raise TimeoutError(f"Timeout waiting for response to {send_message!r}")

    def ask(self, send_message: str, recv_code: int = 0, timeout_ms: int = 10000) -> str:
        self.send(send_message)

        func = send_message.split("(", 1)[0]
        target_prefix = f"{recv_code},{func},".lower()

        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            remaining = int(max(1, (deadline - time.time()) * 1000))
            for line in self.recv(timeout_ms=remaining):
                low = line.lower()

                if low.startswith("remoteex "):
                    continue
                if low.startswith("4,") or low.startswith("5,"):
                    continue

                if low.startswith(target_prefix):
                    return line[len(target_prefix):]

        raise TimeoutError(f"Timeout waiting for data response to {send_message!r}")

    # -------------------------
    # Camera ops (unchanged)
    # -------------------------

    def set_single_acquisition(self, exposure_time_ms: int) -> None:
        self.send_and_wait(f"CamParamSet(Acquire,Exposure,{exposure_time_ms}ms)")
        self.exposure_time = exposure_time_ms
        self.num_exposures = 1
        self.mode = CameraMode.SingleAcquisition

    def set_analog_integration(self, exposure_time_ms: int, num: int) -> None:
        self.send_and_wait(f"CamParamSet(AI,Exposure,{exposure_time_ms}ms)")
        self.exposure_time = exposure_time_ms
        self.send_and_wait(f"CamParamSet(AI,NrExposures,{num})")
        self.num_exposures = num
        self.mode = CameraMode.AnalogIntegration

    def set_sequence(self, exposure_time_ms: int, num: int) -> None:
        self.send_and_wait(f"CamParamSet(Acquire,Exposure,{exposure_time_ms}ms)")
        self.exposure_time = exposure_time_ms
        self.send_and_wait("SeqParamSet(AcquisitionMode,Acquire)")
        self.send_and_wait(f"SeqParamSet(NoOfLoops,{num})")
        self.num_exposures = num
        self.mode = CameraMode.Sequence

    def acq_start(self) -> None:
        self.send_and_wait(
            {
                CameraMode.SingleAcquisition: "AcqStart(Acquire)",
                CameraMode.AnalogIntegration: "AcqStart(AI)",
                CameraMode.Sequence: "SeqStart()",
            }[self.mode]
        )

    def wait_idle(self) -> None:
        initial_wait_ms = (
            self.exposure_time * self.num_exposures
            if self.mode != CameraMode.SingleAcquisition
            else self.exposure_time
        )
        time.sleep(initial_wait_ms / 1000.0)

        status_cmd = "SeqStatus()" if self.mode == CameraMode.Sequence else "AcqStatus()"
        while self.ask(status_cmd) != "idle":
            time.sleep(0.01)

    def acq_and_wait(self) -> None:
        self.acq_start()
        self.wait_idle()

    def save(self, path: str) -> None:
        if self.mode == CameraMode.Sequence:
            p = path.replace(".img", "_000.img")
            self.send_and_wait(f"SeqSave(Img,{p},1)")
            while not self.ask("AsyncCommandStatus()").startswith("0,0,0,"):
                time.sleep(0.01)
        else:
            self.send_and_wait(f"ImgSave(Current,Img,{path},1)")

    def delete(self) -> None:
        self.send_and_wait("SeqDelete()" if self.mode == CameraMode.Sequence else "ImgDelete(All)")

    def get_camera_name(self) -> str:
        return self.ask("ImgStatusGet(Current,Token,Camera,CameraName)")

    def get_image_width(self) -> int:
        return int(self.ask("CamParamGet(Setup,Dcam3SetupProp_Image Width)"))

    def get_image_height(self) -> int:
        return int(self.ask("CamParamGet(Setup,Dcam3SetupProp_Image Height)"))

    def get_bit_depth(self) -> int:
        return int(self.ask("CamParamGet(Setup,Dcam3SetupProp_BitPerChannel)"))

    # -------------------------
    # Greetings drain
    # -------------------------

    def _drain_greetings(self, timeout_s: float = 0.2) -> None:
        assert self._sock_cmd is not None
        end = time.time() + timeout_s
        self._sock_cmd.settimeout(0.05)
        try:
            while time.time() < end:
                try:
                    chunk = self._sock_cmd.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                self._rxbuf.extend(chunk)
                while True:
                    i = self._rxbuf.find(b"\r")
                    if i < 0:
                        break
                    del self._rxbuf[:i + 1]
        finally:
            self._sock_cmd.settimeout(None)

    # -------------------------
    # Context manager
    # -------------------------

    def __enter__(self) -> "RemoteExClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()
