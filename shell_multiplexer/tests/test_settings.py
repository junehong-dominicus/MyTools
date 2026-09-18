import json

from settings import DEFAULT_FONT_SIZE, DEFAULT_LAYOUT_MODE, load_settings_file, save_settings_file


def test_round_trip(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, "2V", {1: "C:\\a", 2: "C:\\b"}, font_size=14)

    mode, paths, font_size = load_settings_file(path)

    assert mode == "2V"
    assert paths == {1: "C:\\a", 2: "C:\\b"}
    assert font_size == 14


def test_round_trip_defaults_font_size_when_not_given(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, "1", {})

    _, _, font_size = load_settings_file(path)

    assert font_size == DEFAULT_FONT_SIZE


def test_missing_file_returns_defaults(tmp_path):
    path = str(tmp_path / "missing.json")

    mode, paths, font_size = load_settings_file(path)

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE


def test_malformed_json_returns_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")

    mode, paths, font_size = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE


def test_unknown_mode_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "99", "panes": {}}))

    mode, _, _ = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE


def test_non_string_mode_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": 2, "panes": {}}))

    mode, _, _ = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE


def test_unrecognized_font_size_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {}, "font_size": 5}))

    _, _, font_size = load_settings_file(str(path))

    assert font_size == DEFAULT_FONT_SIZE


def test_non_int_font_size_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {}, "font_size": "10"}))

    _, _, font_size = load_settings_file(str(path))

    assert font_size == DEFAULT_FONT_SIZE


def test_non_integer_pane_key_is_skipped(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"not-a-number": {"start_path": "C:\\x"}}}))

    _, paths, _ = load_settings_file(str(path))

    assert paths == {}


def test_top_level_list_returns_defaults(tmp_path):
    # Valid JSON, but not an object -- config.get() would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("[]")

    mode, paths, font_size = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE


def test_top_level_null_returns_defaults(tmp_path):
    # Valid JSON, but config.get() on None would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("null")

    mode, paths, font_size = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE


def test_panes_as_list_returns_defaults(tmp_path):
    # "panes" is present but shaped wrong -- .items() on a list raises
    # AttributeError. This must fall back to defaults (including layout_mode),
    # the same as a fully malformed file, not raise out of load_settings_file.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "2", "panes": [1, 2]}))

    mode, paths, font_size = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE


def test_loading_a_config_saved_before_font_size_existed(tmp_path):
    # Backward compatibility: a config file written before this feature
    # existed has no "font_size" key at all -- must default, not crash.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "2", "panes": {"1": {"start_path": "C:\\a"}}}))

    mode, paths, font_size = load_settings_file(str(path))

    assert mode == "2"
    assert paths == {1: "C:\\a"}
    assert font_size == DEFAULT_FONT_SIZE
