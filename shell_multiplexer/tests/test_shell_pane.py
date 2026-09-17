import os
import time

from shell_pane import ShellPane
from terminal_widget import TerminalWidget


def _pump_until(qapp, predicate, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.05)
    return False


def test_pane_falls_back_to_home_dir_when_path_missing(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, str(tmp_path / "does_not_exist"))

    pane.start_shell()

    assert pane.path_edit.text() == os.path.expanduser("~")


def test_pane_shows_status_on_spawn_failure(qapp, monkeypatch):
    def boom(self, cwd):
        raise RuntimeError("no powershell.exe")

    monkeypatch.setattr(TerminalWidget, "start", boom)
    pane = ShellPane(1, os.path.expanduser("~"))

    pane.start_shell()

    assert "Failed to start shell" in pane.status_label.text()


def test_exit_signal_updates_status(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.start_shell()

    pane.terminal.exited.emit(0)

    assert "exited" in pane.status_label.text().lower()


def test_valid_path_is_kept_as_is(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, str(tmp_path))

    pane.start_shell()

    assert pane.path_edit.text() == str(tmp_path)


def test_restart_does_not_leak_process_and_does_not_show_exited_status(qapp, tmp_path):
    # Regression test for the Restart leak (Finding 1): ShellPane's Restart
    # button re-invokes start_shell() -> TerminalWidget.start() ->
    # PtyBackend.spawn() on the SAME TerminalWidget/PtyBackend instances
    # (they are not recreated). Uses a real shell process end-to-end so the
    # actual reader-thread/exited-signal interaction is exercised, not a
    # mock of it.
    pane = ShellPane(1, str(tmp_path))
    pane.start_shell()

    assert _pump_until(qapp, lambda: pane.terminal.backend.is_alive())
    first_proc = pane.terminal.backend._proc
    first_thread = pane.terminal.backend._thread

    pane.start_shell()  # simulates clicking Restart

    assert _pump_until(
        qapp, lambda: pane.terminal.backend.is_alive() and pane.terminal.backend._proc is not first_proc
    )

    # Give the old process/thread a moment to actually wind down, and give
    # any (buggy) stale queued `exited` signal a chance to arrive and update
    # the status label.
    _pump_until(qapp, lambda: not first_proc.isalive() and not first_thread.is_alive(), timeout=3)
    for _ in range(10):
        qapp.processEvents()
        time.sleep(0.05)

    assert not first_thread.is_alive(), "old reader thread must not survive a restart"
    assert not first_proc.isalive(), "old powershell.exe process must not survive a restart"
    assert pane.terminal.backend.is_alive()
    assert "exited" not in pane.status_label.text().lower()

    pane.terminate()
