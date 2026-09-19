import os
import sys
from unittest.mock import patch

import main
from layout import LAYOUT_MODES
from main import MainWindow
from settings import (
    CONFIG_DIR, CONFIG_FILENAME, DEFAULT_CONFIG_NAME, DEFAULT_FONT_SIZE, DEFAULT_LAYOUT_MODE,
    FONT_SIZES, config_file_path, save_settings_file,
)
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
    window.panes[0].path_edit.setText("/tmp/kept")

    window.build_panes("2")

    assert window.panes[0].path_edit.text() == "/tmp/kept"


def test_settings_round_trip_across_instances(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")

    window = MainWindow(config_dir=config_dir)
    window.build_panes("2V")
    window.panes[0].path_edit.setText("/tmp/somewhere")
    window.font_size_combo.setCurrentText("16")
    window.save_current_config()

    window2 = MainWindow(config_dir=config_dir)

    assert len(window2.panes) == 2
    assert window2.current_mode == "2V"
    assert window2.panes[0].path_edit.text() == "/tmp/somewhere"
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

    # QMessageBox.warning() opens a real modal event loop -- under the
    # offscreen QPA platform (see conftest.py) nothing exists to click its
    # OK button, so it blocks forever unless patched out, same as any other
    # test that exercises a path showing one.
    with patch("main.QInputDialog.getText", return_value=("   ", True)), \
         patch("main.QMessageBox.warning") as warning_mock:
        window.save_config_as()

    items = [window.config_combo.itemText(i) for i in range(window.config_combo.count())]
    assert items == [DEFAULT_CONFIG_NAME]
    warning_mock.assert_called_once()


def test_save_config_as_with_blank_name_does_not_silently_no_op(qapp, monkeypatch, tmp_path):
    # Regression test: a blank name used to hit the same early return as a
    # cancelled dialog, with zero feedback -- indistinguishable from "nothing
    # happened". It must warn the user instead.
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    with patch("main.QInputDialog.getText", return_value=("", True)), \
         patch("main.QMessageBox.warning") as warning_mock:
        window.save_config_as()

    warning_mock.assert_called_once()


def test_save_config_as_cancelled_shows_no_warning(qapp, monkeypatch, tmp_path):
    # Cancelling the dialog (ok=False) is the one case that must stay silent.
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    with patch("main.QInputDialog.getText", return_value=("", False)), \
         patch("main.QMessageBox.warning") as warning_mock, \
         patch("main.QMessageBox.critical") as critical_mock:
        window.save_config_as()

    warning_mock.assert_not_called()
    critical_mock.assert_not_called()


def test_write_config_shows_error_and_does_not_update_combo_when_save_fails(qapp, monkeypatch, tmp_path):
    # Regression test: save_settings_file() failing (disk full, permissions,
    # etc.) used to only print() -- invisible for a GUI app launched via
    # Finder/`open` with no attached console. Must surface an error instead
    # of looking exactly like a successful, no-op save.
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    monkeypatch.setattr("main.save_settings_file", lambda *a, **k: False)

    with patch("main.QMessageBox.critical") as critical_mock:
        ok = window._write_config("newconfig")

    assert ok is False
    critical_mock.assert_called_once()
    items = [window.config_combo.itemText(i) for i in range(window.config_combo.count())]
    assert "newconfig" not in items


def test_write_config_shows_error_when_makedirs_fails(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    def boom(*a, **k):
        raise OSError("Read-only file system")

    monkeypatch.setattr(os, "makedirs", boom)

    with patch("main.QMessageBox.critical") as critical_mock:
        ok = window._write_config("newconfig")

    assert ok is False
    critical_mock.assert_called_once()


def test_write_config_returns_true_and_shows_no_error_on_success(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))

    with patch("main.QMessageBox.critical") as critical_mock:
        ok = window._write_config("newconfig")

    assert ok is True
    critical_mock.assert_not_called()
    items = [window.config_combo.itemText(i) for i in range(window.config_combo.count())]
    assert "newconfig" in items


def test_load_selected_config_applies_its_settings(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")
    window = MainWindow(config_dir=config_dir)

    with patch("main.QInputDialog.getText", return_value=("alt", True)):
        window.build_panes("2V")
        window.panes[0].path_edit.setText("/tmp/alt")
        window.font_size_combo.setCurrentText("18")
        window.save_config_as()

    window.build_panes("1")  # simulate switching away without saving
    window.font_size_combo.setCurrentText("10")

    window.config_combo.setCurrentText("alt")
    window.load_selected_config()

    assert len(window.panes) == 2
    assert window.panes[0].path_edit.text() == "/tmp/alt"
    assert window.current_font_size == 18
    assert window.font_size_combo.currentText() == "18"


def test_migrates_legacy_single_file_config(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    monkeypatch.chdir(tmp_path)
    save_settings_file(CONFIG_FILENAME, "3T", {1: "/tmp/legacy"}, font_size=14)

    window = MainWindow()  # default config_dir, resolved relative to cwd

    assert not os.path.exists(CONFIG_FILENAME)
    assert os.path.exists(os.path.join("configs", "default.json"))
    assert window.current_mode == "3T"
    assert window.current_font_size == 14
    assert window.panes[0].path_edit.text() == "/tmp/legacy"


def test_history_carries_forward_across_rebuild(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.panes[0].terminal.load_history(["~/project $ git status"])

    window.build_panes("2")

    assert window.panes[0].terminal.get_history() == ["~/project $ git status"]


def test_settings_round_trip_across_instances_includes_history(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")

    window = MainWindow(config_dir=config_dir)
    window.panes[0].terminal.load_history(["~/project $ ls", "~/project $ git status"])
    window.save_current_config()

    window2 = MainWindow(config_dir=config_dir)

    assert window2.panes[0].terminal.get_history() == ["~/project $ ls", "~/project $ git status"]


def test_history_survives_shrink_and_grow_shell_count(qapp, monkeypatch, tmp_path):
    # Regression test for Finding 3: SHELL COUNT 4 -> 1 tears down panes
    # 2-4. Going back to 4 must not have lost pane 2's history, even though
    # it had no live pane in between.
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.build_panes("4")
    pane2 = next(p for p in window.panes if p.pane_id == 2)
    pane2.terminal.load_history(["~/project $ pane2 command"])

    window.build_panes("1")  # panes 2-4 torn down
    window.build_panes("4")  # panes 2-4 rebuilt

    pane2_again = next(p for p in window.panes if p.pane_id == 2)
    assert pane2_again.terminal.get_history() == ["~/project $ pane2 command"]


def test_history_survives_shrink_then_save_then_fresh_instance(qapp, monkeypatch, tmp_path):
    # Regression test for Finding 3: shrinking SHELL COUNT to 1 and then
    # clicking Save must not silently overwrite the on-disk history for
    # panes 2-4 with nothing, even though they have no live pane at Save
    # time and are never visible in the UI again before the fresh instance
    # loads the config back from disk.
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")
    window = MainWindow(config_dir=config_dir)
    window.build_panes("4")
    pane2 = next(p for p in window.panes if p.pane_id == 2)
    pane2.terminal.load_history(["~/project $ pane2 command"])

    window.build_panes("1")  # panes 2-4 torn down, never touched again
    window.save_current_config()

    window2 = MainWindow(config_dir=config_dir)
    window2.build_panes("4")
    pane2_reloaded = next(p for p in window2.panes if p.pane_id == 2)
    assert pane2_reloaded.terminal.get_history() == ["~/project $ pane2 command"]


def test_load_config_restores_history(qapp, monkeypatch, tmp_path):
    # Regression test for Finding 4: the existing round-trip test only
    # exercises history restoration through a *fresh* MainWindow
    # constructor. This exercises the _load_config path (as invoked by the
    # Load button, via load_selected_config) directly on an existing
    # instance.
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.panes[0].terminal.load_history(["~/project $ ls"])
    window.save_current_config()
    # save_current_config()/_write_config() already selects the just-saved
    # config in config_combo (via refresh_config_list(select=name)), so
    # load_selected_config() below reloads that same config.
    assert window.config_combo.currentText() == DEFAULT_CONFIG_NAME

    window.panes[0].terminal.load_history([])  # simulate history no longer visible in the UI
    window.load_selected_config()

    assert window.panes[0].terminal.get_history() == ["~/project $ ls"]


def test_default_config_dir_anchors_to_script_dir_when_not_frozen(qapp, monkeypatch):
    # Regression test: CONFIG_DIR ("configs") is a bare relative path, which
    # only resolves next to main.py if the process's cwd happens to already
    # be there. A packaged .app launched via Finder/`open` gets an arbitrary
    # (often read-only) cwd instead -- default_config_dir() must anchor to
    # main.py's own directory rather than trusting the ambient cwd.
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    expected = os.path.join(os.path.dirname(os.path.abspath(main.__file__)), CONFIG_DIR)
    assert MainWindow.default_config_dir() == expected


def test_default_config_dir_uses_application_support_when_frozen(qapp, monkeypatch):
    # A frozen .app's own bundle directory is read-only/disposable -- writes
    # must go to the standard per-user config location instead.
    monkeypatch.setattr(sys, "_MEIPASS", "/some/bundle/path", raising=False)

    expected = os.path.join(
        os.path.expanduser("~/Library/Application Support/MultiTerminal"), CONFIG_DIR,
    )
    assert MainWindow.default_config_dir() == expected
