import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from terminal_widget import TerminalWidget

# Placeholder text shown in the history dialog's list when the pane has no
# recorded history yet, in place of a blank list.
_NO_HISTORY_PLACEHOLDER = "No commands recorded yet"


def _copy_selection_to_clipboard(history_list: QListWidget) -> None:
    """Copy the history dialog's currently-selected rows to the clipboard,
    newline-joined. Split out from _show_history so it can be exercised
    directly in tests without going through a QShortcut."""
    selected = history_list.selectedItems()
    if not selected:
        return
    QGuiApplication.clipboard().setText("\n".join(item.text() for item in selected))


class ShellPane(QFrame):
    def __init__(self, pane_id: int, start_path: str, parent=None):
        super().__init__(parent)
        self.pane_id = pane_id
        self.setObjectName("ShellPane")
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QFrame()
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)

        header_layout.addWidget(QLabel(f"SHELL {pane_id}"))

        self.path_edit = QLineEdit(start_path)
        header_layout.addWidget(self.path_edit, 2)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        header_layout.addWidget(browse_btn)

        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self.start_shell)
        header_layout.addWidget(restart_btn)

        history_btn = QPushButton("History")
        history_btn.clicked.connect(self._show_history)
        header_layout.addWidget(history_btn)

        layout.addWidget(header)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.terminal = TerminalWidget()
        self.terminal.exited.connect(self._on_shell_exited)
        layout.addWidget(self.terminal, 1)

    def start_shell(self) -> None:
        path = self.path_edit.text().strip() or os.path.expanduser("~")
        if not os.path.isdir(path):
            path = os.path.expanduser("~")
            self.path_edit.setText(path)
            self.status_label.setText("Path not found — using home directory")
        else:
            self.status_label.setText("")

        try:
            self.terminal.start(path)
        except Exception as e:
            self.status_label.setText(f"Failed to start shell: {e}")

    def _on_shell_exited(self, code: int) -> None:
        self.status_label.setText(f"Shell exited (code {code}) — click Restart")

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select start directory", self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)

    def _show_history(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Shell {self.pane_id} History")
        # Without this, every History click leaves behind a hidden QDialog
        # instance that's never destroyed until the pane itself is -- this
        # dialog is created fresh each time rather than cached/reused.
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog_layout = QVBoxLayout(dialog)

        history = self.terminal.get_history()
        history_list = QListWidget()
        # Allow selecting multiple entries so the copy shortcut below has
        # something to act on -- view and copy (via normal list selection +
        # Ctrl+C) is the whole point of this dialog.
        history_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if history:
            history_list.addItems(history)
        else:
            placeholder = QListWidgetItem(_NO_HISTORY_PLACEHOLDER)
            placeholder.setFlags(Qt.NoItemFlags)
            history_list.addItem(placeholder)
        dialog_layout.addWidget(history_list)
        dialog.resize(500, 400)

        copy_shortcut = QShortcut(QKeySequence(QKeySequence.Copy), dialog)
        copy_shortcut.activated.connect(lambda: _copy_selection_to_clipboard(history_list))

        dialog.show()
        history_list.scrollToBottom()

    def terminate(self) -> None:
        self.terminal.backend.terminate()
