import time

from pty_backend import PtyBackend


def _pump_until(qapp, predicate, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.05)
    return False


def test_spawn_and_echo(qapp, tmp_path):
    backend = PtyBackend()
    received = []
    backend.output_received.connect(received.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    backend.write("Write-Output HELLO_MARKER\r")

    found = _pump_until(qapp, lambda: any("HELLO_MARKER" in chunk for chunk in received))

    assert found
    backend.terminate()


def test_is_alive_true_after_spawn(qapp, tmp_path):
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)

    assert backend.is_alive()

    backend.terminate()


def test_exited_signal_fires_on_shell_exit(qapp, tmp_path):
    backend = PtyBackend()
    exited_codes = []
    backend.exited.connect(exited_codes.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    backend.write("exit\r")

    found = _pump_until(qapp, lambda: len(exited_codes) > 0)

    assert found


def test_resize_does_not_raise(qapp, tmp_path):
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)

    backend.resize(120, 40)  # should not raise

    backend.terminate()
