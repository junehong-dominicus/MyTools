import pytest
import json
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox
from main import MainWindow
from shell_pane import ShellPane
from settings import config_file_path, save_settings_file


def test_growing_layout_keeps_existing_shell_session(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    original = window.panes[0]
    original.terminate = Mock()
    window.build_panes("4")
    assert window.panes[0] is original
    original.terminate.assert_not_called()
    window.close()


def test_shrinking_layout_stops_only_removed_sessions(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.build_panes("3")
    first, second, third = window.panes
    for pane in window.panes:
        pane.terminate = Mock()
    window.build_panes("1")
    assert window.panes == [first]
    first.terminate.assert_not_called()
    second.terminate.assert_called_once()
    third.terminate.assert_called_once()
    window.close()


def test_save_targets_loaded_config_not_combo_selection(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    directory = str(tmp_path / "configs")
    window = MainWindow(config_dir=directory)
    other = config_file_path(directory, "other")
    save_settings_file(other, "2", {}, 8)
    window.refresh_config_list(select="other")
    window.current_font_size = 18
    window.save_current_config()
    assert json.loads((tmp_path / "configs/default.json").read_text())["font_size"] == 18
    assert json.loads((tmp_path / "configs/other.json").read_text())["font_size"] == 8
    assert window.active_config_name == "default"
    assert "Saved configuration" in window.statusBar().currentMessage()
    window.close()


@pytest.mark.parametrize("invalid", ["[]", '{"panes":{"1":{"start_path":[]}}}', '{"panes":{"1":null}}'])
def test_invalid_config_load_keeps_current_session(qapp, monkeypatch, tmp_path, invalid):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    original = window.panes[0]
    (tmp_path / "configs/broken.json").write_text(invalid)
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    window._load_config("broken")
    assert window.panes[0] is original
    assert window.active_config_name == "default"
    warning.assert_called_once()
    window.close()


def test_load_replaces_history_instead_of_merging_previous_config(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    directory = str(tmp_path / "configs")
    window = MainWindow(config_dir=directory)
    window.build_panes("2")
    window.panes[1].terminal.load_history(["previous secret command"])
    save_settings_file(config_file_path(directory, "empty"), "2", {})
    window._load_config("empty")
    assert window.panes[1].terminal.get_history() == []
    window.close()


def test_cancel_removal_keeps_sessions_and_restores_combo(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.shell_count_combo.setCurrentText("4")
    original = list(window.panes)
    for pane in window.panes:
        monkeypatch.setattr(pane.terminal.backend, "is_alive", lambda: True)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    window.shell_count_combo.setCurrentText("1")
    assert window.panes == original
    assert window.shell_count_combo.currentText() == "4"
    window.close()


def test_hidden_pane_path_survives_save_and_fresh_load(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    directory = str(tmp_path / "configs")
    window = MainWindow(config_dir=directory)
    window.build_panes("2")
    window.panes[1].path_edit.setText("remember-this-path")
    window.build_panes("1")
    window.save_current_config()
    fresh = MainWindow(config_dir=directory)
    fresh.build_panes("2")
    assert fresh.panes[1].path_edit.text() == "remember-this-path"
    fresh.close()
    window.close()


def test_failed_save_reports_error_without_changing_active_config(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    monkeypatch.setattr("main.save_settings_file", lambda *args: False)
    assert window._write_config("new") is False
    assert window.active_config_name == "default"
    critical.assert_called_once()
    window.close()
