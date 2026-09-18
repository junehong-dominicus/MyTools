import os
from unittest.mock import patch

from layout import LAYOUT_MODES
from main import MainWindow
from settings import DEFAULT_CONFIG_NAME, DEFAULT_FONT_SIZE, DEFAULT_LAYOUT_MODE, FONT_SIZES, config_file_path, save_settings_file
from shell_pane import ShellPane


def test_starts_with_default_layout_mode(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    assert window.current_mode == DEFAULT_LAYOUT_MODE
    assert len(window.panes) == 1


def test_starts_with_default_font_size(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    assert window.current_font_size == DEFAULT_FONT_SIZE
    assert window.panes[0].terminal._font.pointSize() == DEFAULT_FONT_SIZE


def test_shell_count_combo_lists_all_layout_modes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    items = [window.shell_count_combo.itemText(i) for i in range(window.shell_count_combo.count())]

    assert items == LAYOUT_MODES


def test_font_size_combo_lists_all_font_sizes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    items = [window.font_size_combo.itemText(i) for i in range(window.font_size_combo.count())]

    assert items == [str(s) for s in FONT_SIZES]


def test_changing_font_size_applies_to_all_current_panes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.build_panes("4")

    window.font_size_combo.setCurrentText("18")

    assert window.current_font_size == 18
    assert all(p.terminal._font.pointSize() == 18 for p in window.panes)


def test_new_panes_adopt_current_font_size(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.font_size_combo.setCurrentText("14")

    window.build_panes("2")  # rebuild -- new panes must not reset to the default

    assert all(p.terminal._font.pointSize() == 14 for p in window.panes)


def test_build_panes_creates_correct_count_and_ids(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    window.build_panes("4")

    assert len(window.panes) == 4
    assert sorted(p.pane_id for p in window.panes) == [1, 2, 3, 4]


def test_build_panes_2v_creates_two_panes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    window.build_panes("2V")

    assert len(window.panes) == 2
    assert sorted(p.pane_id for p in window.panes) == [1, 2]


def test_build_panes_3t_creates_three_panes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    window.build_panes("3T")

    assert len(window.panes) == 3
    assert sorted(p.pane_id for p in window.panes) == [1, 2, 3]


def test_build_panes_carries_forward_paths(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.panes[0].path_edit.setText("C:\\Kept")

    window.build_panes("2")

    assert window.panes[0].path_edit.text() == "C:\\Kept"


def test_settings_round_trip_across_instances(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")

    window = MainWindow(config_dir=config_dir)
    window.build_panes("2V")
    window.panes[0].path_edit.setText("C:\\Somewhere")
    window.font_size_combo.setCurrentText("16")
    window.save_current_config()

    window2 = MainWindow(config_dir=config_dir)

    assert len(window2.panes) == 2
    assert window2.current_mode == "2V"
    assert window2.panes[0].path_edit.text() == "C:\\Somewhere"
    assert window2.current_font_size == 16
    assert window2.font_size_combo.currentText() == "16"
    assert window2.panes[0].terminal._font.pointSize() == 16


def test_close_event_terminates_all_panes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    terminated = []
    monkeypatch.setattr(ShellPane, "terminate", lambda self: terminated.append(self.pane_id))
    # Pre-seed a 3-pane default config so construction builds all 3 panes in a
    # single build_panes() call. (Constructing with the default mode and then
    # calling build_panes("3") afterward would legitimately terminate the
    # discarded default pane too, which is correct rebuild behavior but not
    # what this test is checking.)
    config_dir = str(tmp_path / "configs")
    os.makedirs(config_dir)
    save_settings_file(config_file_path(config_dir, DEFAULT_CONFIG_NAME), "3", {})
    window = MainWindow(config_dir=config_dir)

    window.close()

    assert sorted(terminated) == [1, 2, 3]


def test_config_combo_lists_default_after_construction(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    items = [window.config_combo.itemText(i) for i in range(window.config_combo.count())]

    assert items == [DEFAULT_CONFIG_NAME]
    assert window.config_combo.currentText() == DEFAULT_CONFIG_NAME


def test_save_config_as_adds_and_selects_new_entry(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    with patch("main.QInputDialog.getText", return_value=("my rig", True)):
        window.save_config_as()

    items = [window.config_combo.itemText(i) for i in range(window.config_combo.count())]
    assert "my_rig" in items
    assert window.config_combo.currentText() == "my_rig"


def test_save_config_as_rejects_blank_name(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    with patch("main.QInputDialog.getText", return_value=("   ", True)):
        window.save_config_as()

    items = [window.config_combo.itemText(i) for i in range(window.config_combo.count())]
    assert items == [DEFAULT_CONFIG_NAME]


def test_load_selected_config_applies_its_settings(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")
    window = MainWindow(config_dir=config_dir)

    with patch("main.QInputDialog.getText", return_value=("alt", True)):
        window.build_panes("2V")
        window.panes[0].path_edit.setText("C:\\Alt")
        window.font_size_combo.setCurrentText("18")
        window.save_config_as()

    window.build_panes("1")  # simulate switching away without saving
    window.font_size_combo.setCurrentText("10")

    window.config_combo.setCurrentText("alt")
    window.load_selected_config()

    assert len(window.panes) == 2
    assert window.panes[0].path_edit.text() == "C:\\Alt"
    assert window.current_font_size == 18
    assert window.font_size_combo.currentText() == "18"


def test_migrates_legacy_single_file_config(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    monkeypatch.chdir(tmp_path)
    save_settings_file("shell_config.json", "3T", {1: "C:\\Legacy"}, font_size=14)

    window = MainWindow()  # default config_dir, resolved relative to cwd

    assert not os.path.exists("shell_config.json")
    assert os.path.exists(os.path.join("configs", "default.json"))
    assert window.current_mode == "3T"
    assert window.current_font_size == 14
    assert window.panes[0].path_edit.text() == "C:\\Legacy"
