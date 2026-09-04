import threading
import webbrowser

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QObject

from scanner import EmbeddedSystemScanner

# ─────────────────────────────────────────────────────────────────────────────
# Network scan dialog (Qt port of the original scanner's tkinter/customtkinter UI),
# backed by the same EmbeddedSystemScanner business logic.
# ─────────────────────────────────────────────────────────────────────────────

COLUMNS = ("status", "name", "ip", "manufacturer", "mac", "version")
HEADERS = ("", "Device Name", "IP Address", "Manufacturer", "MAC Address", "Firmware Version")


class ScanResultSignal(QObject):
    finished = Signal(dict)


class ScanDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Scanner — Embedded System / Embedded System Network Discovery")
        self.resize(900, 480)
        # Non-modal: keep serial panes usable while a scan runs.
        self.setModal(False)

        self.scanner = EmbeddedSystemScanner()
        self.scan_in_progress = False

        self.result_signal = ScanResultSignal()
        self.result_signal.finished.connect(self._on_scan_finished)

        layout = QVBoxLayout(self)

        # Header row: interface selector + scan button
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Interfaces:"))

        self.interface_combo = QComboBox()
        self.interface_combo.addItems(["Ethernet & Wi-Fi", "Ethernet", "Wi-Fi"])
        header_row.addWidget(self.interface_combo)

        header_row.addStretch()

        self.scan_btn = QPushButton("Start Scan")
        self.scan_btn.clicked.connect(self.toggle_scan)
        header_row.addWidget(self.scan_btn)

        layout.addLayout(header_row)

        # Results table
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)

        # Status line
        self.status_label = QLabel("Ready to scan")
        layout.addWidget(self.status_label)

    def toggle_scan(self):
        if self.scan_in_progress:
            self.stop_scan()
            return

        self.scan_in_progress = True
        self.scan_btn.setText("Stop Scan")
        selected_iface = self.interface_combo.currentText()
        self.status_label.setText(f"Scanning {selected_iface}...")
        self.table.setRowCount(0)

        thread = threading.Thread(target=self._run_scan, args=(selected_iface,), daemon=True)
        thread.start()

    def stop_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Stopping...")
        self.status_label.setText("Stopping scan...")
        self.scanner.stop()

    def _run_scan(self, selected_iface):
        results = self.scanner.full_scan(target_interface=selected_iface)
        # scanner runs on a worker thread; hop back to the Qt thread to touch widgets.
        self.result_signal.finished.emit(results)

    def _on_scan_finished(self, results):
        self.table.setRowCount(0)
        for row, (ip, data) in enumerate(results.items()):
            self.table.insertRow(row)
            status = "●" if "Configuration WebUI" in data["services"] else "○"
            values = (status, data["name"], ip, data["manufacturer"], data["mac"], data.get("version", "—"))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

        self.scan_in_progress = False
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Start Scan")
        if self.scanner.was_stopped:
            self.status_label.setText(f"Scan stopped. Found {len(results)} device(s).")
        else:
            self.status_label.setText(f"Scan complete. Found {len(results)} device(s).")

    def on_row_double_clicked(self, row, _column):
        ip_item = self.table.item(row, COLUMNS.index("ip"))
        if not ip_item:
            return
        webbrowser.open(f"http://{ip_item.text()}:8000")

    def closeEvent(self, event):
        # Let an in-flight scan finish on its own thread; just hide the dialog.
        self.hide()
        event.ignore()
