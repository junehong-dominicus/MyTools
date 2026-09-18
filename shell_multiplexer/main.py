import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from common.ui_theme import apply_industrial_theme

from layout import LAYOUT_MODES, compute_grid_rows
from settings import (
    CONFIG_DIR, DEFAULT_CONFIG_NAME, DEFAULT_FONT_SIZE, DEFAULT_LAYOUT_MODE, FONT_SIZES,
    config_file_path, list_config_names, load_settings_file, migrate_legacy_config,
    sanitize_config_name, save_settings_file,
)
from shell_pane import ShellPane

if sys.platform == 'win32':
    import ctypes
    myappid = u'mytools.shell_multiplexer.app'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class MainWindow(QMainWindow):
    def __init__(self, config_dir: str = CONFIG_DIR):
        super().__init__()
        self.config_dir = config_dir
        self.setWindowTitle("MyTools — Shell Multiplexer")
        self.setMinimumSize(1200, 800)

        self.panes: list[ShellPane] = []
        self.current_mode = DEFAULT_LAYOUT_MODE
        self.current_font_size = DEFAULT_FONT_SIZE
        self.pane_area_layout = None

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)

        toolbar = QFrame()
        toolbar.setFixedHeight(20)
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(10, 0, 10, 0)

        title = QLabel("MYTOOLS — SHELL MULTIPLEXER")
        title.setStyleSheet("color: #3498DB; font-size: 12px; font-weight: bold;")
        t_layout.addWidget(title)
        t_layout.addStretch()

        t_layout.addWidget(QLabel("SHELL COUNT:"))
        self.shell_count_combo = QComboBox()
        self.shell_count_combo.addItems(LAYOUT_MODES)
        self.shell_count_combo.setFixedWidth(70)
        self.shell_count_combo.setFixedHeight(16)
        self.shell_count_combo.setStyleSheet("padding: 0px 4px;")
        t_layout.addWidget(self.shell_count_combo)

        t_layout.addWidget(QLabel("FONT SIZE:"))
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems([str(s) for s in FONT_SIZES])
        self.font_size_combo.setFixedWidth(55)
        self.font_size_combo.setFixedHeight(16)
        self.font_size_combo.setStyleSheet("padding: 0px 4px;")
        t_layout.addWidget(self.font_size_combo)

        t_layout.addWidget(QLabel("CONFIG:"))
        self.config_combo = QComboBox()
        self.config_combo.setFixedWidth(100)
        self.config_combo.setFixedHeight(16)
        self.config_combo.setStyleSheet("padding: 0px 4px;")
        t_layout.addWidget(self.config_combo)

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(16)
        save_btn.setStyleSheet("padding: 0px 10px;")
        save_btn.clicked.connect(self.save_current_config)
        t_layout.addWidget(save_btn)

        save_as_btn = QPushButton("Save As…")
        save_as_btn.setFixedHeight(16)
        save_as_btn.setStyleSheet("padding: 0px 10px;")
        save_as_btn.clicked.connect(self.save_config_as)
        t_layout.addWidget(save_as_btn)

        load_btn = QPushButton("Load")
        load_btn.setFixedHeight(16)
        load_btn.setStyleSheet("padding: 0px 10px;")
        load_btn.clicked.connect(self.load_selected_config)
        t_layout.addWidget(load_btn)

        outer_layout.addWidget(toolbar)

        self.pane_area = QWidget()
        self.pane_area_layout = QVBoxLayout(self.pane_area)
        self.pane_area_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.pane_area)

        migrate_legacy_config(self.config_dir)
        default_path = config_file_path(self.config_dir, DEFAULT_CONFIG_NAME)
        initial_mode, initial_paths, initial_font_size = load_settings_file(default_path)
        self.current_font_size = initial_font_size

        self.shell_count_combo.blockSignals(True)
        self.shell_count_combo.setCurrentText(initial_mode)
        self.shell_count_combo.blockSignals(False)
        self.shell_count_combo.currentTextChanged.connect(self._on_shell_count_changed)

        self.font_size_combo.blockSignals(True)
        self.font_size_combo.setCurrentText(str(initial_font_size))
        self.font_size_combo.blockSignals(False)
        self.font_size_combo.currentTextChanged.connect(self._on_font_size_changed)

        self.build_panes(initial_mode, initial_paths)

        if os.path.exists(default_path):
            self.refresh_config_list(select=DEFAULT_CONFIG_NAME)
        else:
            self._write_config(DEFAULT_CONFIG_NAME)

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
        pane.terminal.set_font_size(self.current_font_size)
        self.panes.append(pane)
        pane.start_shell()
        return pane

    def _on_shell_count_changed(self, text: str) -> None:
        self.build_panes(text)

    def _on_font_size_changed(self, text: str) -> None:
        self.current_font_size = int(text)
        for pane in self.panes:
            pane.terminal.set_font_size(self.current_font_size)

    def refresh_config_list(self, select: str | None = None) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        names = list_config_names(self.config_dir)

        self.config_combo.blockSignals(True)
        self.config_combo.clear()
        self.config_combo.addItems(names)
        self.config_combo.blockSignals(False)

        if select and select in names:
            self.config_combo.setCurrentText(select)

    def _write_config(self, name: str) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        pane_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        save_settings_file(config_file_path(self.config_dir, name), self.current_mode, pane_paths, self.current_font_size)
        self.refresh_config_list(select=name)

    def _load_config(self, name: str) -> None:
        mode, paths, font_size = load_settings_file(config_file_path(self.config_dir, name))
        self.current_font_size = font_size

        self.font_size_combo.blockSignals(True)
        self.font_size_combo.setCurrentText(str(font_size))
        self.font_size_combo.blockSignals(False)

        self.shell_count_combo.blockSignals(True)
        self.shell_count_combo.setCurrentText(mode)
        self.shell_count_combo.blockSignals(False)

        self.build_panes(mode, paths)

    def save_current_config(self) -> None:
        name = self.config_combo.currentText() or DEFAULT_CONFIG_NAME
        self._write_config(name)

    def save_config_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Config As", "Config name:")
        if not ok or not name.strip():
            return
        safe_name = sanitize_config_name(name)
        if not safe_name:
            QMessageBox.warning(self, "Invalid name", "Please use letters, numbers, - or _.")
            return
        self._write_config(safe_name)

    def load_selected_config(self) -> None:
        name = self.config_combo.currentText()
        if name:
            self._load_config(name)

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
