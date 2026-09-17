import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from common.ui_theme import apply_industrial_theme

from layout import LAYOUT_MODES, compute_grid_rows
from settings import CONFIG_FILENAME, DEFAULT_LAYOUT_MODE, load_settings_file, save_settings_file
from shell_pane import ShellPane

if sys.platform == 'win32':
    import ctypes
    myappid = u'mytools.shell_multiplexer.app'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class MainWindow(QMainWindow):
    def __init__(self, config_path: str = CONFIG_FILENAME):
        super().__init__()
        self.config_path = config_path
        self.setWindowTitle("MyTools — Shell Multiplexer")
        self.setMinimumSize(1200, 800)

        self.panes: list[ShellPane] = []
        self.current_mode = DEFAULT_LAYOUT_MODE
        self.pane_area_layout = None

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)

        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        t_layout = QHBoxLayout(toolbar)

        title = QLabel("MYTOOLS — SHELL MULTIPLEXER")
        title.setStyleSheet("color: #3498DB; font-size: 18px; font-weight: bold;")
        t_layout.addWidget(title)
        t_layout.addStretch()

        t_layout.addWidget(QLabel("SHELL COUNT:"))
        self.shell_count_combo = QComboBox()
        self.shell_count_combo.addItems(LAYOUT_MODES)
        self.shell_count_combo.setFixedWidth(70)
        t_layout.addWidget(self.shell_count_combo)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        t_layout.addWidget(save_btn)

        outer_layout.addWidget(toolbar)

        self.pane_area = QWidget()
        self.pane_area_layout = QVBoxLayout(self.pane_area)
        self.pane_area_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.pane_area)

        initial_mode, initial_paths = load_settings_file(self.config_path)
        self.shell_count_combo.blockSignals(True)
        self.shell_count_combo.setCurrentText(initial_mode)
        self.shell_count_combo.blockSignals(False)
        self.shell_count_combo.currentTextChanged.connect(self._on_shell_count_changed)

        self.build_panes(initial_mode, initial_paths)

    def build_panes(self, mode: str, initial_paths: dict[int, str] | None = None) -> None:
        prior_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        if initial_paths:
            prior_paths.update(initial_paths)

        for pane in self.panes:
            pane.terminate()
            pane.setParent(None)
            pane.deleteLater()
        self.panes = []
        self.current_mode = mode

        while self.pane_area_layout.count():
            item = self.pane_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = compute_grid_rows(mode)
        main_splitter = QSplitter(Qt.Vertical)
        for row in rows:
            if len(row) == 1:
                pane = self._make_pane(row[0], prior_paths)
                main_splitter.addWidget(pane)
            else:
                row_splitter = QSplitter(Qt.Horizontal)
                for pane_id in row:
                    pane = self._make_pane(pane_id, prior_paths)
                    row_splitter.addWidget(pane)
                main_splitter.addWidget(row_splitter)

        self.pane_area_layout.addWidget(main_splitter)

    def _make_pane(self, pane_id: int, prior_paths: dict[int, str]) -> ShellPane:
        path = prior_paths.get(pane_id, os.path.expanduser("~"))
        pane = ShellPane(pane_id, path)
        self.panes.append(pane)
        pane.start_shell()
        return pane

    def _on_shell_count_changed(self, text: str) -> None:
        self.build_panes(text)

    def save_settings(self) -> None:
        pane_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        save_settings_file(self.config_path, self.current_mode, pane_paths)

    def closeEvent(self, event) -> None:
        for pane in self.panes:
            pane.terminate()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    apply_industrial_theme(app)

    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, "common", "app_icon.ico")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "common", "app_icon.ico")

    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
