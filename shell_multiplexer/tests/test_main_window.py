from main import MainWindow
from settings import DEFAULT_PANE_COUNT, save_settings_file
from shell_pane import ShellPane


def test_starts_with_default_pane_count(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))

    assert len(window.panes) == DEFAULT_PANE_COUNT


def test_build_panes_creates_correct_count_and_ids(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))

    window.build_panes(4)

    assert len(window.panes) == 4
    assert sorted(p.pane_id for p in window.panes) == [1, 2, 3, 4]


def test_build_panes_carries_forward_paths(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))
    window.panes[0].path_edit.setText("C:\\Kept")

    window.build_panes(2)

    assert window.panes[0].path_edit.text() == "C:\\Kept"


def test_settings_round_trip_across_instances(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_path = str(tmp_path / "cfg.json")

    window = MainWindow(config_path=config_path)
    window.build_panes(2)
    window.panes[0].path_edit.setText("C:\\Somewhere")
    window.save_settings()

    window2 = MainWindow(config_path=config_path)

    assert len(window2.panes) == 2
    assert window2.panes[0].path_edit.text() == "C:\\Somewhere"


def test_close_event_terminates_all_panes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    terminated = []
    monkeypatch.setattr(ShellPane, "terminate", lambda self: terminated.append(self.pane_id))
    # Pre-seed a 3-pane config so construction builds all 3 panes in a single
    # build_panes() call. (Constructing with the default count and then calling
    # build_panes(3) afterward would legitimately terminate the discarded
    # default pane too, which is correct rebuild behavior but not what this
    # test is checking.)
    config_path = str(tmp_path / "cfg.json")
    save_settings_file(config_path, 3, {})
    window = MainWindow(config_path=config_path)

    window.close()

    assert sorted(terminated) == [1, 2, 3]
