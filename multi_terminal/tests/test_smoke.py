from main import MainWindow
from shell_pane import ShellPane


def test_main_window_constructs(qapp, monkeypatch):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow()
    assert window.windowTitle() == "MyTools — MultiTerminal"
    window.close()
