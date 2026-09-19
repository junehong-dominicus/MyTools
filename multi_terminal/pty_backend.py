import fcntl
import logging
import os
import pty
import select
import signal
import struct
import termios
import threading

from PySide6.QtCore import QObject, Signal


def _login_shell() -> str:
    return os.environ.get("SHELL", "/bin/zsh")


class PtyBackend(QObject):
    output_received = Signal(str)
    exited = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pid = None
        self._fd = None
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
        if self._pid is not None:
            self._suppress_exit_signal = True
            self.terminate()
            self._suppress_exit_signal = False

        pid, fd = pty.fork()
        if pid == 0:
            # Child: pty.fork() has already made us the session leader with
            # the pty slave as our controlling terminal. Exec a login+
            # interactive shell (-il) so it reads .zshrc/.zprofile etc, the
            # same as a real Terminal.app window -- aliases, PATH tweaks,
            # prompt themes and the like all come from there.
            try:
                os.chdir(cwd)
            except OSError:
                pass
            os.environ["TERM"] = "xterm-256color"
            shell = _login_shell()
            try:
                os.execvp(shell, [shell, "-il"])
            except OSError:
                pass
            os._exit(1)

        self._pid = pid
        self._fd = fd
        self._set_winsize(columns, lines)
        self._stop = False
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _set_winsize(self, columns: int, lines: int) -> None:
        try:
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HHHH", lines, columns, 0, 0))
        except OSError:
            pass

    def _read_loop(self) -> None:
        while not self._stop:
            try:
                ready, _, _ = select.select([self._fd], [], [], 0.2)
            except (OSError, ValueError):
                break
            if not ready:
                continue
            try:
                data = os.read(self._fd, 4096)
            except OSError:
                # EIO is what the pty master gives you once the child side
                # has gone away -- the normal way this loop ends.
                break
            if not data:
                break
            self.output_received.emit(data.decode("utf-8", errors="replace"))

        code = self._reap()
        if not self._suppress_exit_signal:
            self.exited.emit(code)

    def _reap(self) -> int:
        if self._pid is None:
            return -1
        try:
            wpid, status = os.waitpid(self._pid, os.WNOHANG)
            if wpid == 0:
                # Not dead yet (e.g. terminate() only just signaled it) --
                # block until it actually exits rather than reporting a
                # fake/incomplete status.
                wpid, status = os.waitpid(self._pid, 0)
        except ChildProcessError:
            return -1
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        if os.WIFSIGNALED(status):
            return -os.WTERMSIG(status)
        return -1

    def write(self, text: str) -> None:
        if self._fd is not None and self.is_alive():
            try:
                os.write(self._fd, text.encode("utf-8"))
            except OSError:
                pass

    def resize(self, columns: int, lines: int) -> None:
        if self._fd is not None and self.is_alive():
            self._set_winsize(columns, lines)

    def is_alive(self) -> bool:
        if self._pid is None:
            return False
        try:
            os.kill(self._pid, 0)
        except OSError:
            return False
        return True

    def terminate(self) -> None:
        self._stop = True
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGKILL)
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2)
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        self._pid = None
