import json

from settings import DEFAULT_PANE_COUNT, load_settings_file, save_settings_file


def test_round_trip(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, 2, {1: "C:\\a", 2: "C:\\b"})

    count, paths = load_settings_file(path)

    assert count == 2
    assert paths == {1: "C:\\a", 2: "C:\\b"}


def test_missing_file_returns_defaults(tmp_path):
    path = str(tmp_path / "missing.json")

    count, paths = load_settings_file(path)

    assert count == DEFAULT_PANE_COUNT
    assert paths == {}


def test_malformed_json_returns_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")

    count, paths = load_settings_file(str(path))

    assert count == DEFAULT_PANE_COUNT
    assert paths == {}


def test_out_of_range_count_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"shell_count": 99, "panes": {}}))

    count, _ = load_settings_file(str(path))

    assert count == DEFAULT_PANE_COUNT


def test_non_integer_pane_key_is_skipped(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"shell_count": 1, "panes": {"not-a-number": {"start_path": "C:\\x"}}}))

    _, paths = load_settings_file(str(path))

    assert paths == {}


def test_top_level_list_returns_defaults(tmp_path):
    # Valid JSON, but not an object -- config.get() would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("[]")

    count, paths = load_settings_file(str(path))

    assert count == DEFAULT_PANE_COUNT
    assert paths == {}


def test_top_level_null_returns_defaults(tmp_path):
    # Valid JSON, but config.get() on None would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("null")

    count, paths = load_settings_file(str(path))

    assert count == DEFAULT_PANE_COUNT
    assert paths == {}


def test_panes_as_list_returns_defaults(tmp_path):
    # "panes" is present but shaped wrong -- .items() on a list raises
    # AttributeError. This must fall back to defaults (including shell_count),
    # the same as a fully malformed file, not raise out of load_settings_file.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"shell_count": 2, "panes": [1, 2]}))

    count, paths = load_settings_file(str(path))

    assert count == DEFAULT_PANE_COUNT
    assert paths == {}
