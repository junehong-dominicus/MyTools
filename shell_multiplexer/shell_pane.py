import os

from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from terminal_widget import TerminalWidget


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

    def terminate(self) -> None:
        self.terminal.backend.terminate()
