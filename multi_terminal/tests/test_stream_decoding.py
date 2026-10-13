"""Reader logic tests with OS calls mocked; these can also run on Windows."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock
import sys


def test_utf8_survives_split_pty_reads(monkeypatch, qapp):
    if sys.platform == "win32":
        for module in ("fcntl", "termios", "pty"):
            monkeypatch.setitem(sys.modules, module, Mock())
    spec = importlib.util.spec_from_file_location("reader_under_test", Path(__file__).resolve().parents[1] / "pty_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    backend = module.PtyBackend()
    backend._fd = 123
    chunks = iter([bytes([0xe2]), bytes([0x82, 0xac]), b""])
    monkeypatch.setattr(module.select, "select", lambda *args: ([123], [], []))
    monkeypatch.setattr(module.os, "read", lambda *args: next(chunks))
    monkeypatch.setattr(backend, "_reap", lambda: 0)
    received = []
    backend.output_received.connect(received.append)
    backend._read_loop()
    assert "".join(received) == "\u20ac"
