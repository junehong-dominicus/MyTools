from main import MainWindow


def test_main_window_constructs(qapp):
    window = MainWindow()
    assert window.windowTitle() == "MyTools — Shell Multiplexer"
