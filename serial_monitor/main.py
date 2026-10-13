import sys
import os
import re
import shutil
import time
import threading
import json
import serial.tools.list_ports
from datetime import datetime

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QPushButton, QTextEdit, QSplitter,
                             QFrame, QGroupBox, QMenu, QLineEdit, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal, QObject, QUrl
from PySide6.QtGui import QFont, QTextCursor, QIcon, QDesktopServices

# Windows Taskbar Icon Fix
if sys.platform == 'win32':
    import ctypes
    myappid = u'mytools.serial_monitor.app' # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Add own dir to path for the locally-vendored common/ theme package
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from common.ui_theme import apply_industrial_theme, COLOR_ACCENT_RED, COLOR_ACCENT_GREEN

from serial_engine import SerialEngine
from scan_dialog import ScanDialog

# ─────────────────────────────────────────────────────────────────────────────
# MyTools - Serial Monitor + Network Scanner
# (migrated from serial_monitor_v2, with a network-scanner feature
# added behind a SCAN toolbar button)
# ─────────────────────────────────────────────────────────────────────────────

class DataSignal(QObject):
    received = Signal(str)
    failed = Signal(object, str)

class CommandLineEdit(QLineEdit):
    """QLineEdit with shell-style Up/Down command history."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = []          # oldest -> newest
        self._index = 0            # position in history; == len == "editing a new line"
        self._pending = ""         # text typed before browsing into history

    def add_history(self, text):
        # Store on submit; skip empties and immediate duplicates.
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._index = len(self._history)
        self._pending = ""

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Up:
            if self._history:
                if self._index == len(self._history):
                    self._pending = self.text()   # remember the in-progress line
                self._index = max(0, self._index - 1)
                self.setText(self._history[self._index])
                self.end(False)
            return
        if key == Qt.Key_Down:
            if self._history:
                if self._index < len(self._history):
                    self._index += 1
                self.setText(self._pending if self._index >= len(self._history)
                             else self._history[self._index])
                self.end(False)
            return
        super().keyPressEvent(event)

class SerialPane(QFrame):
    def __init__(self, pane_id):
        super().__init__()
        self.pane_id = pane_id
        self.engine = None
        self.log_path = None
        self.setObjectName("SerialPane")
        self.setFrameShape(QFrame.StyledPanel)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        # Header
        self.header = QFrame()
        self.header.setFixedHeight(45)
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(10, 0, 10, 0)

        self.status_led = QLabel("●")
        self.status_led.setStyleSheet(f"color: {COLOR_ACCENT_RED}; font-size: 20px;")
        self.header_layout.addWidget(self.status_led)

        self.header_layout.addWidget(QLabel(f"PORT {pane_id}"))

        self.port_combo = QComboBox()
        self.refresh_ports()
        if self.port_combo.count() >= pane_id:
            self.port_combo.setCurrentIndex(pane_id - 1)
        self.header_layout.addWidget(self.port_combo, 2)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "115200", "460800", "921600"])
        self.baud_combo.setCurrentText("115200")
        self.header_layout.addWidget(self.baud_combo, 1)

        self.conn_btn = QPushButton("CONNECT")
        self.conn_btn.setFixedWidth(100)
        self.conn_btn.setStyleSheet(f"color: {COLOR_ACCENT_GREEN};")
        self.conn_btn.clicked.connect(self.toggle_connection)
        self.header_layout.addWidget(self.conn_btn)

        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.clicked.connect(self.clear_log)
        self.header_layout.addWidget(self.clear_btn)

        self.open_log_btn = QPushButton("OPEN LOG FILE")
        self.open_log_btn.setFixedWidth(120)
        self.open_log_btn.setEnabled(False)
        self.open_log_btn.clicked.connect(self.open_log_file)
        self.header_layout.addWidget(self.open_log_btn)

        self.layout.addWidget(self.header)

        # Log View
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Connect a serial port to view received data.")
        self.log_view.document().setMaximumBlockCount(10000)
        self.log_view.setToolTip("Latest 10,000 lines. Full received output is saved in the log files.")
        self.log_view.setFont(QFont("Consolas", 10))
        self.log_view.setStyleSheet("background-color: #0D0D0D; color: #00FF00; border: none;")
        self.layout.addWidget(self.log_view)

        # Command input row (send to device). Disabled until connected.
        self.input_row = QFrame()
        input_layout = QHBoxLayout(self.input_row)
        input_layout.setContentsMargins(0, 4, 0, 0)

        self.cmd_input = CommandLineEdit()
        self.cmd_input.setPlaceholderText("Type a command, press Enter to send (↑/↓ history)…")
        self.cmd_input.setFont(QFont("Consolas", 10))
        self.cmd_input.returnPressed.connect(self.send_command)
        input_layout.addWidget(self.cmd_input, 1)

        # Line ending. Default "CR (\r)". Note: the Embedded System product-test parser is
        # byte-oriented (e.g. "s1" checks an exact length of 2), so for those
        # commands select "None"; strstr-based commands tolerate a trailing CR.
        self.eol_combo = QComboBox()
        self.eol_combo.addItems(["None", "CR (\\r)", "LF (\\n)", "CRLF (\\r\\n)"])
        self.eol_combo.setCurrentText("CR (\\r)")
        self.eol_combo.setFixedWidth(110)
        input_layout.addWidget(self.eol_combo)

        self.send_btn = QPushButton("SEND")
        self.send_btn.setFixedWidth(70)
        self.send_btn.clicked.connect(self.send_command)
        input_layout.addWidget(self.send_btn)

        self.input_row.setEnabled(False)  # enabled on connect
        self.layout.addWidget(self.input_row)

        # Signals
        self.data_signal = DataSignal()
        self.data_signal.received.connect(self.append_log)
        self.data_signal.failed.connect(self._on_connection_lost)

    def refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports if ports else ["No Ports Found"])
        if current in ports:
            self.port_combo.setCurrentText(current)

    def disconnect(self):
        if self.engine:
            self.log_path = self.engine.get_log_path() or self.log_path
            self.engine.stop()
            self.engine = None
        self.status_led.setStyleSheet(f"color: {COLOR_ACCENT_RED}; font-size: 18px;")
        self.conn_btn.setText("CONNECT")
        self.conn_btn.setStyleSheet(f"color: {COLOR_ACCENT_GREEN};")
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.input_row.setEnabled(False)

    def _on_connection_lost(self, engine, message):
        if engine is not self.engine:
            return
        self.disconnect()
        self.append_log(f"\n[DISCONNECTED] {message}\n")

    def toggle_connection(self):
        if self.engine:
            self.disconnect()
            return
        port = self.port_combo.currentText()
        if port == "No Ports Found":
            return
        baud = int(self.baud_combo.currentText())
        engine = SerialEngine(port, baud, lambda t: self.data_signal.received.emit(t),
                              on_error=lambda message: self.data_signal.failed.emit(engine, message))
        self.engine = engine
        success, msg = engine.start()
        if success:
            self.status_led.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 18px;")
            self.conn_btn.setText("DISCONNECT")
            self.conn_btn.setStyleSheet(f"color: {COLOR_ACCENT_RED};")
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.input_row.setEnabled(True)
            self.log_path = engine.get_log_path()
            self.open_log_btn.setEnabled(True)
            self.cmd_input.setFocus()
        else:
            self.engine = None
            self.append_log(f"\n[ERROR] {msg}\n")

    def send_command(self):
        if not (self.engine and self.engine.running):
            return
        text = self.cmd_input.text()
        if text == "":
            return
        eol = {"None": "", "CR (\\r)": "\r", "LF (\\n)": "\n", "CRLF (\\r\\n)": "\r\n"}[self.eol_combo.currentText()]
        if self.engine.send(text + eol):
            self.append_log(f"\n>> {text}\n")   # echo what we sent
            self.cmd_input.add_history(text)
            self.cmd_input.clear()
        else:
            self.append_log("\n[ERROR] send failed\n")

    def open_log_file(self):
        if self.engine and self.engine.running:
            self.log_path = self.engine.get_log_path()  # pick up rotation
        if not self.log_path or not os.path.exists(self.log_path):
            self.append_log("\n[ERROR] no log file yet\n")
            return
        try:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.log_path)):
                self.append_log("\n[ERROR] could not open log file\n")
        except Exception as e:
            self.append_log(f"\n[ERROR] could not open log: {e}\n")

    def append_log(self, text):
        self.log_view.insertPlainText(text)
        self.log_view.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.log_view.clear()

DEFAULT_PANE_COUNT = 1
MAX_PANE_COUNT = 4

CONFIG_DIR = "configs"
DEFAULT_CONFIG_NAME = "default"
LEGACY_CONFIG_FILENAME = "serial_config_v2.json"  # pre-multi-config location


def config_path(name):
    return os.path.join(CONFIG_DIR, f"{name}.json")


def sanitize_config_name(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name.strip())


class MyToolsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyTools — Serial Monitor")
        self.setMinimumSize(1200, 800)

        self.scan_dialog = None  # created lazily on first SCAN click
        self.panes = []
        self.active_config_name = DEFAULT_CONFIG_NAME
        self._pane_settings = {}
        self.pane_area_layout = None

        # Window icon is set by main() before show() for correct taskbar display

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        t_layout = QHBoxLayout(toolbar)

        title = QLabel("MYTOOLS — SERIAL MONITOR")
        title.setStyleSheet(f"color: #3498DB; font-size: 18px; font-weight: bold;")
        t_layout.addWidget(title)

        t_layout.addStretch()

        t_layout.addWidget(QLabel("PORT COUNT:"))
        self.port_count_combo = QComboBox()
        self.port_count_combo.setToolTip("Keep connected ports; removing panes disconnects only those ports.")
        self.port_count_combo.addItems([str(n) for n in range(1, MAX_PANE_COUNT + 1)])
        self.port_count_combo.setCurrentText(str(DEFAULT_PANE_COUNT))
        self.port_count_combo.setFixedWidth(60)
        self.port_count_combo.currentTextChanged.connect(self.on_port_count_changed)
        t_layout.addWidget(self.port_count_combo)

        refresh_btn = QPushButton("⟳ Refresh Ports")
        refresh_btn.clicked.connect(self.refresh_all_ports)
        t_layout.addWidget(refresh_btn)

        t_layout.addWidget(QLabel("CONFIG:"))
        self.config_combo = QComboBox()
        self.config_combo.setFixedWidth(120)
        t_layout.addWidget(self.config_combo)

        save_btn = QPushButton("Save")
        save_btn.setToolTip("Save changes to the active configuration.")
        save_btn.clicked.connect(self.save_current_config)
        t_layout.addWidget(save_btn)

        save_as_btn = QPushButton("Save As…")
        save_as_btn.clicked.connect(self.save_config_as)
        t_layout.addWidget(save_as_btn)

        load_btn = QPushButton("Load")
        load_btn.setToolTip("Disconnect current ports and apply the selected configuration.")
        load_btn.clicked.connect(self.load_selected_config)
        t_layout.addWidget(load_btn)

        scan_btn = QPushButton("⚲ NETWORK SCAN")
        scan_btn.setStyleSheet(
            "background-color: #F5A623; color: #1A1A1A; font-weight: bold;"
        )
        scan_btn.clicked.connect(self.open_scan_dialog)
        t_layout.addWidget(scan_btn)

        layout.addWidget(toolbar)

        # Panes live in their own container so the splitter tree can be torn
        # down and rebuilt when the port count changes.
        self.pane_area = QWidget()
        self.pane_area_layout = QVBoxLayout(self.pane_area)
        self.pane_area_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pane_area)

        self.build_panes(DEFAULT_PANE_COUNT)
        self._migrate_legacy_config()
        if not os.path.exists(config_path(DEFAULT_CONFIG_NAME)):
            self._write_config(DEFAULT_CONFIG_NAME)
        else:
            self._load_config(DEFAULT_CONFIG_NAME)
            self.refresh_config_list(select=DEFAULT_CONFIG_NAME)

    def build_panes(self, count):
        """Change the pane layout while keeping retained connections alive."""
        self._pane_settings.update({p.pane_id: (p.port_combo.currentText(), p.baud_combo.currentText())
                                    for p in self.panes})
        prior_settings = self._pane_settings.copy()
        reusable = {}
        for pane in self.panes:
            pane.setParent(None)
            if pane.pane_id <= count:
                reusable[pane.pane_id] = pane
            else:
                pane.disconnect()
                pane.deleteLater()
        self.panes = []

        while self.pane_area_layout.count():
            item = self.pane_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        main_splitter = QSplitter(Qt.Vertical)
        pane_id = 1
        remaining = count
        while remaining > 0:
            row_size = min(2, remaining)
            if row_size == 1:
                pane = reusable.get(pane_id) or SerialPane(pane_id)
                self.panes.append(pane)
                main_splitter.addWidget(pane)
                pane_id += 1
            else:
                row_splitter = QSplitter(Qt.Horizontal)
                for _ in range(row_size):
                    pane = reusable.get(pane_id) or SerialPane(pane_id)
                    self.panes.append(pane)
                    row_splitter.addWidget(pane)
                    pane_id += 1
                main_splitter.addWidget(row_splitter)
            remaining -= row_size

        self.pane_area_layout.addWidget(main_splitter)

        for pane in self.panes:
            if pane.pane_id in prior_settings:
                port, baud = prior_settings[pane.pane_id]
                pane.port_combo.setCurrentText(port)
                pane.baud_combo.setCurrentText(baud)

    def on_port_count_changed(self, text):
        count = int(text)
        closing = [p for p in self.panes if p.pane_id > count and p.engine]
        if closing and QMessageBox.question(self, "Disconnect ports?",
                f"Removing these panes will disconnect {len(closing)} serial port(s).",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            self.port_count_combo.blockSignals(True)
            self.port_count_combo.setCurrentText(str(len(self.panes)))
            self.port_count_combo.blockSignals(False)
            return
        self.build_panes(count)

    def open_scan_dialog(self):
        if self.scan_dialog is None:
            self.scan_dialog = ScanDialog(self)
        self.scan_dialog.show()
        self.scan_dialog.raise_()
        self.scan_dialog.activateWindow()

    def refresh_all_ports(self):
        for pane in self.panes:
            pane.refresh_ports()

    def _migrate_legacy_config(self):
        if os.path.isdir(CONFIG_DIR) or not os.path.exists(LEGACY_CONFIG_FILENAME):
            return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            shutil.move(LEGACY_CONFIG_FILENAME, config_path(DEFAULT_CONFIG_NAME))
        except OSError as e:
            print(f"Config migration error: {e}")

    def refresh_config_list(self, select=None):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        names = sorted(
            os.path.splitext(f)[0] for f in os.listdir(CONFIG_DIR) if f.endswith(".json")
        )
        if DEFAULT_CONFIG_NAME in names:
            names.remove(DEFAULT_CONFIG_NAME)
            names.insert(0, DEFAULT_CONFIG_NAME)

        self.config_combo.blockSignals(True)
        self.config_combo.clear()
        self.config_combo.addItems(names)
        self.config_combo.blockSignals(False)

        if select and select in names:
            self.config_combo.setCurrentText(select)

    def _build_config_dict(self):
        return {
            "port_count": len(self.panes),
            "panes": {
                str(pane.pane_id): {"port": pane.port_combo.currentText(), "baud": pane.baud_combo.currentText()}
                for pane in self.panes
            },
        }

    def _write_config(self, name):
        config = self._build_config_dict()
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(config_path(name), "w") as f:
                json.dump(config, f, indent=4)
        except OSError as error:
            QMessageBox.critical(self, "Save failed", f"Could not save configuration:\n{error}")
            return False
        self.active_config_name = name
        self.refresh_config_list(select=name)
        self.setWindowTitle(f"MyTools - Serial Monitor [{name}]")
        self.statusBar().showMessage(f"Saved configuration: {name}", 5000)
        return True

    def _apply_config_dict(self, config):
        if not isinstance(config, dict):
            return
        port_count = config.get("port_count", DEFAULT_PANE_COUNT)
        if type(port_count) is not int or not (1 <= port_count <= MAX_PANE_COUNT):
            port_count = DEFAULT_PANE_COUNT
        if port_count != len(self.panes):
            self.port_count_combo.setCurrentText(str(port_count))  # triggers build_panes via signal

        p_cfg = config.get("panes", {})
        if not isinstance(p_cfg, dict):
            return
        for pane in self.panes:
            pane_cfg = p_cfg.get(str(pane.pane_id))
            if not isinstance(pane_cfg, dict):
                continue
            port = pane_cfg.get("port")
            baud = pane_cfg.get("baud")
            if isinstance(port, str):
                pane.port_combo.setCurrentText(port)
            if isinstance(baud, str) and baud in {"9600", "115200", "460800", "921600"}:
                pane.baud_combo.setCurrentText(baud)

    def _load_config(self, name):
        try:
            with open(config_path(name), "r") as f:
                config = json.load(f)
            if not isinstance(config, dict):
                raise ValueError("Configuration must be a JSON object.")
            if not isinstance(config.get("panes", {}), dict):
                raise ValueError("Configuration panes must be a JSON object.")
            for pane_cfg in config.get("panes", {}).values():
                if not isinstance(pane_cfg, dict):
                    raise ValueError("Each pane must be a JSON object.")
                if "port" in pane_cfg and not isinstance(pane_cfg["port"], str):
                    raise ValueError("Serial port names must be text.")
                if "baud" in pane_cfg and pane_cfg["baud"] not in ("9600", "115200", "460800", "921600"):
                    raise ValueError("Unsupported baud rate in configuration.")
            for pane in self.panes:
                pane.disconnect()
            self._pane_settings.clear()
            self._apply_config_dict(config)
        except (ValueError, KeyError, OSError, UnicodeError) as error:
            self.statusBar().showMessage(f"Could not load configuration: {error}", 8000)
            return False
        self.active_config_name = name
        self.setWindowTitle(f"MyTools - Serial Monitor [{name}]")
        self.statusBar().showMessage(f"Loaded configuration: {name}", 5000)
        return True

    def save_current_config(self):
        self._write_config(self.active_config_name)

    def save_config_as(self):
        name, ok = QInputDialog.getText(self, "Save Config As", "Config name:")
        if not ok or not name.strip():
            return
        safe_name = sanitize_config_name(name)
        if not safe_name:
            QMessageBox.warning(self, "Invalid name", "Please use letters, numbers, - or _.")
            return
        if safe_name != self.active_config_name and os.path.exists(config_path(safe_name)):
            if QMessageBox.question(self, "Replace configuration?", f"Replace the saved configuration '{safe_name}'?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
        self._write_config(safe_name)

    def load_selected_config(self):
        name = self.config_combo.currentText()
        if name:
            if any(p.engine for p in self.panes):
                if QMessageBox.question(self, "Load configuration?", "Loading will disconnect the current serial ports.",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                    return
            self._load_config(name)

    def closeEvent(self, event):
        for pane in self.panes:
            pane.disconnect()
        if self.scan_dialog:
            self.scan_dialog.scanner.stop()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    apply_industrial_theme(app)

    # Set app icon before creating/showing any window so Windows taskbar uses it
    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, "app_icon.ico")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_dir, "common", "app_icon.ico")

    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MyToolsApp()
    window.adjustSize()
    screen = app.primaryScreen().availableGeometry()
    x = screen.x() + (screen.width() - window.width()) // 2
    y = screen.y() + (screen.height() - window.height()) // 2
    window.move(x, y)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
