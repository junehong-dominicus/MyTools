import json

from settings import DEFAULT_LAYOUT_MODE, load_settings_file, save_settings_file


def test_round_trip(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, "2V", {1: "C:\\a", 2: "C:\\b"})

    mode, paths = load_settings_file(path)

    assert mode == "2V"
    assert paths == {1: "C:\\a", 2: "C:\\b"}


def test_missing_file_returns_defaults(tmp_path):
    path = str(tmp_path / "missing.json")

    mode, paths = load_settings_file(path)

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}


def test_malformed_json_returns_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")

    mode, paths = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}


def test_unknown_mode_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "99", "panes": {}}))

    mode, _ = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE


def test_non_string_mode_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": 2, "panes": {}}))

    mode, _ = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE


def test_non_integer_pane_key_is_skipped(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"not-a-number": {"start_path": "C:\\x"}}}))

    _, paths = load_settings_file(str(path))

    assert paths == {}


def test_top_level_list_returns_defaults(tmp_path):
    # Valid JSON, but not an object -- config.get() would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("[]")

    mode, paths = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}


def test_top_level_null_returns_defaults(tmp_path):
    # Valid JSON, but config.get() on None would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("null")

    mode, paths = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}


def test_panes_as_list_returns_defaults(tmp_path):
    # "panes" is present but shaped wrong -- .items() on a list raises
    # AttributeError. This must fall back to defaults (including layout_mode),
    # the same as a fully malformed file, not raise out of load_settings_file.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "2", "panes": [1, 2]}))

    mode, paths = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
