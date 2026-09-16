import os

from shell_pane import ShellPane
from terminal_widget import TerminalWidget


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
