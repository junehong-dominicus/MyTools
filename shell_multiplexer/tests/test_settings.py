import json
import os

from settings import (
    DEFAULT_CONFIG_NAME, DEFAULT_FONT_SIZE, DEFAULT_LAYOUT_MODE, MAX_HISTORY_ENTRIES,
    config_file_path, list_config_names, load_settings_file, migrate_legacy_config,
    sanitize_config_name, save_settings_file,
)


def test_round_trip(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, "2V", {1: "C:\\a", 2: "C:\\b"}, font_size=14)

    mode, paths, font_size, histories = load_settings_file(path)

    assert mode == "2V"
    assert paths == {1: "C:\\a", 2: "C:\\b"}
    assert font_size == 14
    assert histories == {1: [], 2: []}


def test_round_trip_defaults_font_size_when_not_given(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, "1", {})

    _, _, font_size, _ = load_settings_file(path)

    assert font_size == DEFAULT_FONT_SIZE


def test_missing_file_returns_defaults(tmp_path):
    path = str(tmp_path / "missing.json")

    mode, paths, font_size, histories = load_settings_file(path)

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE
    assert histories == {}


def test_malformed_json_returns_defaults(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")

    mode, paths, font_size, histories = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE
    assert histories == {}


def test_unknown_mode_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "99", "panes": {}}))

    mode, _, _, _ = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE


def test_non_string_mode_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": 2, "panes": {}}))

    mode, _, _, _ = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE


def test_unrecognized_font_size_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {}, "font_size": 5}))

    _, _, font_size, _ = load_settings_file(str(path))

    assert font_size == DEFAULT_FONT_SIZE


def test_non_int_font_size_falls_back_to_default(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {}, "font_size": "10"}))

    _, _, font_size, _ = load_settings_file(str(path))

    assert font_size == DEFAULT_FONT_SIZE


def test_non_integer_pane_key_is_skipped(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"not-a-number": {"start_path": "C:\\x"}}}))

    _, paths, _, histories = load_settings_file(str(path))

    assert paths == {}
    assert histories == {}


def test_top_level_list_returns_defaults(tmp_path):
    # Valid JSON, but not an object -- config.get() would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("[]")

    mode, paths, font_size, histories = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE
    assert histories == {}


def test_top_level_null_returns_defaults(tmp_path):
    # Valid JSON, but config.get() on None would raise AttributeError.
    path = tmp_path / "cfg.json"
    path.write_text("null")

    mode, paths, font_size, histories = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE
    assert histories == {}


def test_panes_as_list_returns_defaults(tmp_path):
    # "panes" is present but shaped wrong -- .items() on a list raises
    # AttributeError. This must fall back to defaults (including layout_mode),
    # the same as a fully malformed file, not raise out of load_settings_file.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "2", "panes": [1, 2]}))

    mode, paths, font_size, histories = load_settings_file(str(path))

    assert mode == DEFAULT_LAYOUT_MODE
    assert paths == {}
    assert font_size == DEFAULT_FONT_SIZE
    assert histories == {}


def test_loading_a_config_saved_before_font_size_existed(tmp_path):
    # Backward compatibility: a config file written before this feature
    # existed has no "font_size" key at all -- must default, not crash.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "2", "panes": {"1": {"start_path": "C:\\a"}}}))

    mode, paths, font_size, histories = load_settings_file(str(path))

    assert mode == "2"
    assert paths == {1: "C:\\a"}
    assert font_size == DEFAULT_FONT_SIZE
    assert histories == {1: []}


def test_config_file_path_joins_dir_and_name(tmp_path):
    assert config_file_path(str(tmp_path), "myrig") == os.path.join(str(tmp_path), "myrig.json")


def test_sanitize_config_name_keeps_safe_characters():
    assert sanitize_config_name("my-rig_2") == "my-rig_2"


def test_sanitize_config_name_replaces_unsafe_characters():
    assert sanitize_config_name("my rig!/../etc") == "my_rig_____etc"


def test_sanitize_config_name_strips_surrounding_whitespace():
    assert sanitize_config_name("  myrig  ") == "myrig"


def test_list_config_names_on_missing_dir_returns_empty(tmp_path):
    assert list_config_names(str(tmp_path / "nope")) == []


def test_list_config_names_pins_default_first(tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "zebra.json").write_text("{}")
    (config_dir / "default.json").write_text("{}")
    (config_dir / "alpha.json").write_text("{}")

    assert list_config_names(str(config_dir)) == [DEFAULT_CONFIG_NAME, "alpha", "zebra"]


def test_migrate_legacy_config_moves_file_into_dir(tmp_path):
    config_dir = str(tmp_path / "configs")
    legacy_path = str(tmp_path / "shell_config.json")
    save_settings_file(legacy_path, "2V", {1: "C:\\a"}, font_size=14)

    migrate_legacy_config(config_dir, legacy_path=legacy_path)

    assert not os.path.exists(legacy_path)
    mode, paths, font_size, _ = load_settings_file(config_file_path(config_dir, DEFAULT_CONFIG_NAME))
    assert mode == "2V"
    assert paths == {1: "C:\\a"}
    assert font_size == 14


def test_migrate_legacy_config_is_noop_when_dir_already_exists(tmp_path):
    config_dir = str(tmp_path / "configs")
    os.makedirs(config_dir)
    legacy_path = str(tmp_path / "shell_config.json")
    save_settings_file(legacy_path, "2V", {1: "C:\\a"})

    migrate_legacy_config(config_dir, legacy_path=legacy_path)

    assert os.path.exists(legacy_path)  # left alone -- configs/ already exists
    assert not os.path.exists(config_file_path(config_dir, DEFAULT_CONFIG_NAME))


def test_migrate_legacy_config_is_noop_when_legacy_file_missing(tmp_path):
    config_dir = str(tmp_path / "configs")

    migrate_legacy_config(config_dir, legacy_path=str(tmp_path / "shell_config.json"))

    assert not os.path.exists(config_dir)


def test_round_trip_with_history(tmp_path):
    path = str(tmp_path / "cfg.json")
    save_settings_file(path, "1", {1: "C:\\a"}, pane_histories={1: ["cmd1", "cmd2"]})

    _, _, _, histories = load_settings_file(path)

    assert histories == {1: ["cmd1", "cmd2"]}


def test_loading_a_config_saved_before_history_existed(tmp_path):
    # Backward compatibility: a config file with panes but no "history" key
    # at all must default to [] per pane, not crash.
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "2", "panes": {"1": {"start_path": "C:\\a"}}}))

    _, _, _, histories = load_settings_file(str(path))

    assert histories == {1: []}


def test_non_list_history_falls_back_to_empty(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"1": {"start_path": "C:\\a", "history": "not-a-list"}}}))

    _, _, _, histories = load_settings_file(str(path))

    assert histories == {1: []}


def test_history_with_non_string_entries_falls_back_to_empty(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"1": {"start_path": "C:\\a", "history": ["ok", 5]}}}))

    _, _, _, histories = load_settings_file(str(path))

    assert histories == {1: []}


def test_max_history_entries_matches_terminal_widget():
    # settings.py and terminal_widget.py each independently define
    # MAX_HISTORY_ENTRIES = 200 (deliberately, so settings.py stays free of
    # Qt/pyte dependencies). Nothing else enforces they stay equal -- this
    # fails loudly if a future edit changes one without the other.
    from terminal_widget import MAX_HISTORY_ENTRIES as terminal_widget_max

    assert MAX_HISTORY_ENTRIES == terminal_widget_max


def test_history_is_capped_on_load(tmp_path):
    path = tmp_path / "cfg.json"
    long_history = [f"cmd{i}" for i in range(MAX_HISTORY_ENTRIES + 50)]
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"1": {"start_path": "C:\\a", "history": long_history}}}))

    _, _, _, histories = load_settings_file(str(path))

    assert len(histories[1]) == MAX_HISTORY_ENTRIES
    assert histories[1][-1] == f"cmd{MAX_HISTORY_ENTRIES + 49}"
