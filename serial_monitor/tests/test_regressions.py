from types import SimpleNamespace
from unittest.mock import Mock
import threading
import time

import pytest

from scanner import EmbeddedSystemScanner
from serial_engine import SerialEngine
from main import MyToolsApp, validate_config
from scan_dialog import ScanDialog


def test_mdns_devices_are_probed_before_scan_returns(monkeypatch):
    scanner = EmbeddedSystemScanner()
    monkeypatch.setattr(scanner, "get_local_subnets", lambda: [])
    def discover():
        time.sleep(0.02)
        scanner.devices["192.0.2.10"] = {"services": []}
    monkeypatch.setattr(scanner, "mdns_scan", discover)
    probed = []
    monkeypatch.setattr(scanner, "probe_services", probed.append)
    scanner.full_scan()
    assert probed == ["192.0.2.10"]


def test_probe_uses_snapshot_when_device_dictionary_changes(monkeypatch):
    scanner = EmbeddedSystemScanner()
    monkeypatch.setattr(scanner, "get_local_subnets", lambda: [])
    monkeypatch.setattr(scanner, "mdns_scan", lambda: scanner.devices.update({"192.0.2.1": {}, "192.0.2.2": {}}))
    mutated = threading.Event()
    def probe(ip):
        scanner.devices["192.0.2.3"] = {}
        mutated.set()
    monkeypatch.setattr(scanner, "probe_services", probe)
    assert len(scanner.full_scan()) == 3
    assert mutated.is_set()


def _one_arp_subnet(monkeypatch, scanner, arp):
    monkeypatch.setattr(scanner, "get_local_subnets", lambda: [("eth0", "192.0.2.0/24")])
    monkeypatch.setattr(scanner, "iface_category", lambda iface: "Ethernet")
    monkeypatch.setattr(scanner, "_categories_for_selection", lambda target: None)
    monkeypatch.setattr(scanner, "arp_scan", arp)
    monkeypatch.setattr(scanner, "probe_services", lambda ip: None)


def test_mdns_failure_keeps_arp_results(monkeypatch):
    scanner = EmbeddedSystemScanner()
    _one_arp_subnet(monkeypatch, scanner, lambda iface, subnet: scanner.devices.update({"192.0.2.5": {"services": []}}))
    def fail():
        raise OSError("UDP 5353 in use")
    monkeypatch.setattr(scanner, "mdns_scan", fail)
    assert list(scanner.full_scan()) == ["192.0.2.5"]


def test_mdns_runs_concurrently_with_arp(monkeypatch):
    scanner = EmbeddedSystemScanner()
    mdns_started = threading.Event()
    overlapped = []
    _one_arp_subnet(monkeypatch, scanner, lambda iface, subnet: overlapped.append(mdns_started.wait(timeout=2)))
    monkeypatch.setattr(scanner, "mdns_scan", mdns_started.set)
    scanner.full_scan()
    assert overlapped == [True]


@pytest.mark.parametrize("payload", [{"device": "Embedded System"}, {"version": "EMBEDDED SYSTEM v1"}])
def test_device_identity_is_case_insensitive(monkeypatch, payload):
    scanner = EmbeddedSystemScanner()
    scanner.devices["192.0.2.1"] = {"services": []}
    monkeypatch.setattr(scanner, "_get_with_retry", lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: payload))
    scanner.probe_services("192.0.2.1")
    assert scanner.devices["192.0.2.1"]["services"] == ["Configuration WebUI"]


def test_scan_error_restores_controls(qapp, monkeypatch):
    dialog = ScanDialog()
    dialog.scan_in_progress = True
    dialog.scan_btn.setEnabled(False)
    def fail(**kwargs):
        raise RuntimeError("scan failed")
    monkeypatch.setattr(dialog.scanner, "full_scan", fail)
    dialog._run_scan("Ethernet")
    qapp.processEvents()
    assert not dialog.scan_in_progress
    assert dialog.scan_btn.isEnabled()
    assert "scan failed" in dialog.status_label.text()
    dialog.deleteLater()


@pytest.mark.parametrize("failure", ["log", "thread"])
def test_failed_serial_start_closes_resources(monkeypatch, tmp_path, failure):
    monkeypatch.chdir(tmp_path)
    engine = SerialEngine("REVIEW", 115200, None)
    port = Mock(is_open=True)
    monkeypatch.setattr("serial_engine.serial.Serial", lambda *a, **k: port)
    def fail():
        raise OSError("disk full")
    if failure == "log":
        monkeypatch.setattr(engine, "_create_log_file", fail)
    else:
        monkeypatch.setattr("serial_engine.threading.Thread.start", lambda self: fail())
    assert engine.start()[0] is False
    port.close.assert_called_once()
    assert not engine.running
    assert engine.ser is None
    assert engine.log_file is None


def test_serial_utf8_character_split_across_reads(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    received = []
    engine = SerialEngine("REVIEW", 115200, received.append)
    chunks = iter([bytes([0xe2]), bytes([0x82, 0xac])])
    def read(count):
        data = next(chunks)
        if len(data) == 2:
            engine.running = False
        return data
    engine.ser = SimpleNamespace(is_open=True, in_waiting=1, read=read)
    engine.running = True
    monkeypatch.setattr("serial_engine.time.sleep", lambda _: None)
    engine._run()
    assert "".join(received) == "\u20ac"


def test_serial_tail_after_stop_is_dropped_without_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    received = []
    engine = SerialEngine("REVIEW", 115200, received.append)
    engine.log_file = open(tmp_path / "log.txt", "w", encoding="utf-8")
    def read(count):
        # stop() timed out on join and closed the log while this read was pending.
        engine.running = False
        engine.stop()
        return bytes([0xe2])  # incomplete UTF-8 leaves a decoder tail
    engine.ser = SimpleNamespace(is_open=True, in_waiting=1, read=read, close=lambda: None)
    engine.running = True
    monkeypatch.setattr("serial_engine.time.sleep", lambda _: None)
    engine._run()
    assert received == []


@pytest.mark.parametrize("config", [[], None, {"panes": None}, {"panes": {"1": None}}, {"panes": {"1": {"port": [], "baud": 115200}}}])
def test_serial_config_rejects_wrong_shapes(config):
    with pytest.raises(ValueError):
        validate_config(config)


def test_serial_config_applies_valid_settings():
    pane = SimpleNamespace(pane_id=1, port_combo=Mock(), baud_combo=Mock())
    window = SimpleNamespace(panes=[pane])
    MyToolsApp._apply_config_dict(window, {"panes": {"1": {"port": "COM5", "baud": "9600"}}})
    pane.port_combo.setCurrentText.assert_called_once_with("COM5")
    pane.baud_combo.setCurrentText.assert_called_once_with("9600")
