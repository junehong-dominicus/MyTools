import logging
import threading

from PySide6.QtCore import QObject, Signal
from winpty import PtyProcess


class PtyBackend(QObject):
    output_received = Signal(str)
    exited = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._thread = None
        self._stop = False
        # Set immediately before calling terminate() on a still-running prior
        # process from within spawn() (i.e. a deliberate Restart), and reset
        # to False only after that terminate() call returns. terminate()'s
        # self._thread.join(timeout=2) blocks this (calling) thread until the
        # old reader thread's _read_loop actually runs to completion -- and
        # the final exited.emit(code) below happens *before* _read_loop
        # returns (which is what unblocks join()). So whenever the old
        # reader thread reaches that emit, the caller is still blocked inside
        # join() and has not yet had a chance to reset this flag back to
        # False -- it is guaranteed to still be True. That lets us suppress
        # the stale exit signal for a deliberate restart while still
        # emitting normally for a genuine unexpected exit (the shell process
        # exiting/crashing on its own, outside of a spawn()-triggered
        # terminate()).
        self._suppress_exit_signal = False

    def spawn(self, cwd: str, columns: int = 80, lines: int = 24) -> None:
        if self._proc is not None:
            self._suppress_exit_signal = True
            self.terminate()
            self._suppress_exit_signal = False

        self._proc = PtyProcess.spawn(
            ["powershell.exe", "-NoLogo"],
            cwd=cwd,
            dimensions=(lines, columns),
        )
        self._stop = False
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while not self._stop:
            try:
                data = self._proc.read(4096)
            except EOFError:
                break
            except Exception:
                logging.exception("pty_backend read loop error")
                break
            if data:
                self.output_received.emit(data)

        code = self._proc.exitstatus if self._proc.exitstatus is not None else -1
        # Qt signal args are marshalled as a 32-bit signed int here; a real
        # NTSTATUS-style exit code (e.g. STATUS_CONTROL_C_EXIT =
        # 3221225786) would silently wrap into a nonsense negative value.
        if not (-(2**31) <= code < 2**31):
            code = -1
        if not self._suppress_exit_signal:
            self.exited.emit(code)

    def write(self, text: str) -> None:
        if self._proc and self._proc.isalive():
            self._proc.write(text)

    def resize(self, columns: int, lines: int) -> None:
        if self._proc and self._proc.isalive():
            self._proc.setwinsize(lines, columns)

    def is_alive(self) -> bool:
        return bool(self._proc and self._proc.isalive())

    def terminate(self) -> None:
        self._stop = True
        if self._proc:
            self._proc.terminate(force=True)
        if self._thread:
            self._thread.join(timeout=2)
