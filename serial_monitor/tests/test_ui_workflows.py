import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox
from main import MyToolsApp, SerialPane
from scan_dialog import ScanDialog


def make_window(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("main.serial.tools.list_ports.comports", lambda: [SimpleNamespace(device="COM5")])
    return MyToolsApp()


def test_growing_port_layout_keeps_connection(qapp, monkeypatch, tmp_path):
    window = make_window(monkeypatch, tmp_path)
    original = window.panes[0]
    engine = Mock()
    original.engine = engine
    window.port_count_combo.setCurrentText("4")
    assert window.panes[0] is original
    assert original.engine is engine
    engine.stop.assert_not_called()
    window.close()


def test_serial_error_restores_connect_controls(qapp, monkeypatch):
    pane = SerialPane(1)
    engine = Mock()
    pane.engine = engine
    pane.port_combo.setEnabled(False)
    pane.baud_combo.setEnabled(False)
    pane.input_row.setEnabled(True)
    pane._on_connection_lost(engine, "Device unplugged")
    assert pane.engine is None
    assert pane.conn_btn.text() == "CONNECT"
    assert pane.port_combo.isEnabled()
    assert not pane.input_row.isEnabled()
    assert "Device unplugged" in pane.log_view.toPlainText()
    engine.stop.assert_called_once()


def test_stale_serial_error_does_not_disconnect_new_engine(qapp):
    pane = SerialPane(1)
    current = Mock()
    pane.engine = current
    pane._on_connection_lost(Mock(), "old error")
    assert pane.engine is current
    current.stop.assert_not_called()
    pane.disconnect()


def test_serial_save_targets_active_config(qapp, monkeypatch, tmp_path):
    window = make_window(monkeypatch, tmp_path)
    window.config_combo.addItem("other")
    window.config_combo.setCurrentText("other")
    write = Mock()
    monkeypatch.setattr(window, "_write_config", write)
    window.save_current_config()
    write.assert_called_once_with("default")
    window.close()


def test_serial_close_stops_connections(qapp, monkeypatch, tmp_path):
    window = make_window(monkeypatch, tmp_path)
    engine = Mock()
    window.panes[0].engine = engine
    window.close()
    engine.stop.assert_called_once()


def test_scan_web_action_only_opens_identified_device(qapp, monkeypatch):
    dialog = ScanDialog()
    opened = Mock()
    monkeypatch.setattr("scan_dialog.webbrowser.open", opened)
    def device(services):
        return {"name": "Device", "manufacturer": "Unknown", "mac": "Unknown", "services": services}
    dialog._on_scan_finished({"192.0.2.1": device([]), "192.0.2.2": device(["Configuration WebUI"])})
    dialog.table.selectRow(0)
    assert not dialog.open_btn.isEnabled()
    dialog.on_row_double_clicked(0, 0)
    opened.assert_not_called()
    dialog.table.selectRow(1)
    assert dialog.open_btn.isEnabled()
    dialog.open_btn.click()
    opened.assert_called_once_with("http://192.0.2.2:8000")
    dialog.deleteLater()


def test_empty_scan_has_actionable_feedback(qapp):
    dialog = ScanDialog()
    dialog.scan_in_progress = True
    dialog.interface_combo.setEnabled(False)
    dialog.progress.show()
    dialog._on_scan_finished({})
    assert "No devices found" in dialog.status_label.text()
    assert dialog.interface_combo.isEnabled()
    assert dialog.progress.isHidden()
    dialog.deleteLater()


def test_new_serial_panes_choose_distinct_available_ports(qapp, monkeypatch):
    monkeypatch.setattr("main.serial.tools.list_ports.comports", lambda: [SimpleNamespace(device="COM5"), SimpleNamespace(device="COM6")])
    first, second = SerialPane(1), SerialPane(2)
    assert first.port_combo.currentText() == "COM5"
    assert second.port_combo.currentText() == "COM6"


def test_open_log_uses_platform_file_handler(qapp, monkeypatch, tmp_path):
    pane = SerialPane(1)
    path = tmp_path / "received.txt"
    path.write_text("data")
    pane.log_path = str(path)
    opened = Mock(return_value=True)
    monkeypatch.setattr("main.QDesktopServices.openUrl", opened)
    pane.open_log_file()
    assert Path(opened.call_args.args[0].toLocalFile()) == path


@pytest.mark.parametrize("invalid", ["[]", '{"panes":{"1":null}}', '{"panes":{"1":{"port":[]}}}'])
def test_invalid_serial_load_keeps_existing_connection(qapp, monkeypatch, tmp_path, invalid):
    window = make_window(monkeypatch, tmp_path)
    engine = Mock()
    window.panes[0].engine = engine
    (tmp_path / "configs/broken.json").write_text(invalid)
    assert window._load_config("broken") is False
    assert window.panes[0].engine is engine
    engine.stop.assert_not_called()
    assert "Could not load" in window.statusBar().currentMessage()
    window.close()
