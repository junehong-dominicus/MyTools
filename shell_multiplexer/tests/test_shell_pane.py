import os
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QDialog, QListWidget, QPushButton

from shell_pane import _copy_selection_to_clipboard, ShellPane
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


def test_show_history_opens_dialog_listing_terminal_history(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["PS C:\\> git status", "PS C:\\> ls"])

    pane._show_history()

    dialogs = pane.findChildren(QDialog)
    assert len(dialogs) == 1
    history_list = dialogs[0].findChild(QListWidget)
    items = [history_list.item(i).text() for i in range(history_list.count())]
    assert items == ["PS C:\\> git status", "PS C:\\> ls"]

    dialogs[0].close()


def test_history_button_click_opens_dialog(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["cmd one"])
    history_btn = next(b for b in pane.findChildren(QPushButton) if b.text() == "History")

    QTest.mouseClick(history_btn, Qt.LeftButton)

    dialogs = pane.findChildren(QDialog)
    assert len(dialogs) == 1

    dialogs[0].close()


def test_history_dialog_has_delete_on_close_attribute(qapp, monkeypatch):
    # Regression test: without Qt.WA_DeleteOnClose, repeated History clicks
    # accumulate hidden QDialog instances forever (never destroyed until the
    # pane itself is).
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["cmd one"])

    pane._show_history()

    dialog = pane.findChild(QDialog)
    assert dialog.testAttribute(Qt.WA_DeleteOnClose)

    dialog.close()


def test_history_dialog_list_allows_extended_selection(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["cmd one", "cmd two", "cmd three"])

    pane._show_history()

    dialog = pane.findChild(QDialog)
    history_list = dialog.findChild(QListWidget)
    assert history_list.selectionMode() == QAbstractItemView.ExtendedSelection

    dialog.close()


def test_history_dialog_has_copy_shortcut_bound_to_standard_copy_key(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["cmd one", "cmd two"])

    pane._show_history()

    dialog = pane.findChild(QDialog)
    shortcut = dialog.findChild(QShortcut)
    assert shortcut is not None
    assert shortcut.key() == QKeySequence(QKeySequence.Copy)

    dialog.close()


def test_history_dialog_copy_shortcut_copies_selected_lines_newline_joined(qapp, monkeypatch):
    # Verifies the actual wiring end-to-end: select some items, trigger the
    # shortcut's connected slot (activating the QShortcut itself is
    # unreliable off-screen since it depends on window-activation state
    # under the offscreen QPA platform), and check the clipboard. Clipboard
    # access itself works fine under QT_QPA_PLATFORM=offscreen in this
    # environment (verified manually), so this is a real assertion, not a
    # skip.
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["PS C:\\> git status", "PS C:\\> ls", "PS C:\\> pwd"])

    pane._show_history()

    dialog = pane.findChild(QDialog)
    history_list = dialog.findChild(QListWidget)
    history_list.item(0).setSelected(True)
    history_list.item(2).setSelected(True)

    shortcut = dialog.findChild(QShortcut)
    shortcut.activated.emit()

    assert QGuiApplication.clipboard().text() == "PS C:\\> git status\nPS C:\\> pwd"

    dialog.close()


def test_copy_selection_to_clipboard_joins_selected_items_in_isolation(qapp):
    # Exercises the extracted slot logic directly, independent of the
    # dialog/shortcut plumbing.
    history_list = QListWidget()
    history_list.addItems(["one", "two", "three"])
    history_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
    history_list.item(0).setSelected(True)
    history_list.item(1).setSelected(True)

    _copy_selection_to_clipboard(history_list)

    assert QGuiApplication.clipboard().text() == "one\ntwo"


def test_copy_selection_to_clipboard_is_noop_when_nothing_selected(qapp):
    history_list = QListWidget()
    history_list.addItems(["one", "two"])
    QGuiApplication.clipboard().setText("unchanged")

    _copy_selection_to_clipboard(history_list)

    assert QGuiApplication.clipboard().text() == "unchanged"


def test_history_dialog_shows_placeholder_when_history_empty(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))

    pane._show_history()

    dialog = pane.findChild(QDialog)
    history_list = dialog.findChild(QListWidget)
    assert history_list.count() == 1
    assert history_list.item(0).text() == "No commands recorded yet"
    assert not (history_list.item(0).flags() & Qt.ItemIsSelectable)

    dialog.close()


def test_history_dialog_does_not_show_placeholder_when_history_present(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["cmd one"])

    pane._show_history()

    dialog = pane.findChild(QDialog)
    history_list = dialog.findChild(QListWidget)
    items = [history_list.item(i).text() for i in range(history_list.count())]
    assert "No commands recorded yet" not in items

    dialog.close()
