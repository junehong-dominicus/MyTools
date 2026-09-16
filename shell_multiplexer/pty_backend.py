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

    def spawn(self, cwd: str, columns: int = 80, lines: int = 24) -> None:
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
