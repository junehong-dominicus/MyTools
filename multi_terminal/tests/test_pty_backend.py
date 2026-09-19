import os
import time

import pytest

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
    backend.write("echo HELLO_MARKER\r")

    found = _pump_until(qapp, lambda: any("HELLO_MARKER" in chunk for chunk in received))

    assert found
    backend.terminate()


def test_is_alive_true_after_spawn(qapp, tmp_path):
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)

    assert _pump_until(qapp, lambda: backend.is_alive())

    backend.terminate()


def test_exited_signal_fires_on_shell_exit(qapp, tmp_path):
    backend = PtyBackend()
    exited_codes = []
    backend.exited.connect(exited_codes.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    assert _pump_until(qapp, lambda: backend.is_alive())
    backend.write("exit\r")

    found = _pump_until(qapp, lambda: len(exited_codes) > 0)

    assert found


def test_resize_does_not_raise(qapp, tmp_path):
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)

    backend.resize(120, 40)  # should not raise

    backend.terminate()


def test_spawn_tears_down_prior_process_and_thread(qapp, tmp_path):
    # Regression test for the Restart leak: spawn() must terminate any
    # already-running process/reader-thread before starting a new one,
    # since PtyBackend instances are reused (not recreated) across Restart.
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)
    assert _pump_until(qapp, lambda: backend.is_alive())

    first_pid = backend._pid
    first_thread = backend._thread

    backend.spawn(str(tmp_path), columns=80, lines=24)  # simulates clicking Restart
    assert _pump_until(qapp, lambda: backend.is_alive() and backend._pid != first_pid)

    # Give the old thread/process time to actually wind down (spawn() should
    # have already blocked on this via terminate()'s join(), but leave a
    # little slack for the OS to reflect the process death).
    _pump_until(qapp, lambda: not first_thread.is_alive(), timeout=3)

    assert not first_thread.is_alive(), "old reader thread must not survive a restart"
    with pytest.raises(OSError):
        os.kill(first_pid, 0)  # old shell process must not survive a restart
    assert backend.is_alive()
    assert backend._thread is not first_thread

    backend.terminate()


def test_spawn_does_not_emit_stale_exited_signal_for_restarted_process(qapp, tmp_path):
    # Regression test: terminating the old process as part of a deliberate
    # Restart must not fire `exited` for the *new*, still-running process.
    backend = PtyBackend()
    exited_codes = []
    backend.exited.connect(exited_codes.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    assert _pump_until(qapp, lambda: backend.is_alive())

    backend.spawn(str(tmp_path), columns=80, lines=24)  # simulates clicking Restart
    assert _pump_until(qapp, lambda: backend.is_alive())

    # Pump a bit longer to give a (buggy) stale queued signal a chance to
    # arrive if the suppression were not working.
    for _ in range(10):
        qapp.processEvents()
        time.sleep(0.05)

    assert exited_codes == []
    assert backend.is_alive()

    backend.terminate()


def test_reap_reports_exit_status_of_a_normally_exited_child(qapp, tmp_path):
    backend = PtyBackend()
    exited_codes = []
    backend.exited.connect(exited_codes.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    assert _pump_until(qapp, lambda: backend.is_alive())
    backend.write("exit 7\r")

    assert _pump_until(qapp, lambda: len(exited_codes) > 0)
    assert exited_codes == [7]
