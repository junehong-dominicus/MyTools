import json
import os
import re
import shutil

from layout import LAYOUT_MODES

DEFAULT_LAYOUT_MODE = "1"
FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18]
DEFAULT_FONT_SIZE = 10
CONFIG_FILENAME = "shell_config.json"  # legacy single-file location, pre-multi-config
CONFIG_DIR = "configs"
DEFAULT_CONFIG_NAME = "default"
# Kept in sync with terminal_widget.MAX_HISTORY_ENTRIES. Duplicated rather
# than imported: this module has no Qt/pyte dependency and must stay that
# way so it can be tested and reused without them.
MAX_HISTORY_ENTRIES = 200


def save_settings_file(
    path: str,
    layout_mode: str,
    pane_paths: dict[int, str],
    font_size: int = DEFAULT_FONT_SIZE,
    pane_histories: dict[int, list[str]] | None = None,
) -> None:
    pane_histories = pane_histories or {}
    # Iterate the union of pane_paths and pane_histories keys, not just
    # pane_paths: a pane_id can have recorded history while temporarily
    # having no live pane (e.g. SHELL COUNT shrunk below it), in which case
    # pane_paths won't mention it at all. Iterating pane_paths alone would
    # silently drop that pane's history from the saved file even though the
    # caller passed it in.
    pane_ids = set(pane_paths) | set(pane_histories)
    config = {
        "layout_mode": layout_mode,
        "font_size": font_size,
        "panes": {
            str(pid): {"start_path": pane_paths.get(pid, ""), "history": pane_histories.get(pid, [])}
            for pid in pane_ids
        },
    }
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
    except OSError as e:
        print(f"Save error: {e}")


def load_settings_file(path: str) -> tuple[str, dict[int, str], int, dict[int, list[str]]]:
    if not os.path.exists(path):
        return DEFAULT_LAYOUT_MODE, {}, DEFAULT_FONT_SIZE, {}

    try:
        with open(path, "r") as f:
            config = json.load(f)

        layout_mode = config.get("layout_mode", DEFAULT_LAYOUT_MODE)
        if layout_mode not in LAYOUT_MODES:
            layout_mode = DEFAULT_LAYOUT_MODE

        font_size = config.get("font_size", DEFAULT_FONT_SIZE)
        if font_size not in FONT_SIZES:
            font_size = DEFAULT_FONT_SIZE

        pane_paths = {}
        pane_histories = {}
        for pid_str, pane_cfg in config.get("panes", {}).items():
            try:
                pid = int(pid_str)
                pane_paths[pid] = pane_cfg.get("start_path", "")
            except (ValueError, AttributeError):
                continue

            history = pane_cfg.get("history", [])
            if not isinstance(history, list) or not all(isinstance(h, str) for h in history):
                history = []
            pane_histories[pid] = history[-MAX_HISTORY_ENTRIES:]

        return layout_mode, pane_paths, font_size, pane_histories
    except (json.JSONDecodeError, KeyError, OSError, AttributeError, TypeError):
        # AttributeError/TypeError cover valid-JSON-but-wrong-shape configs
        # (e.g. top-level "[]" or "null", or "panes" being a list instead of
        # a dict) where .get()/.items() gets called on something that isn't
        # a dict -- these must fall back to defaults just like malformed
        # JSON, not crash the whole app at startup.
        return DEFAULT_LAYOUT_MODE, {}, DEFAULT_FONT_SIZE, {}


def config_file_path(config_dir: str, name: str) -> str:
    return os.path.join(config_dir, f"{name}.json")


def sanitize_config_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name.strip())


def list_config_names(config_dir: str) -> list[str]:
    if not os.path.isdir(config_dir):
        return []
    names = sorted(
        os.path.splitext(f)[0] for f in os.listdir(config_dir) if f.endswith(".json")
    )
    if DEFAULT_CONFIG_NAME in names:
        names.remove(DEFAULT_CONFIG_NAME)
        names.insert(0, DEFAULT_CONFIG_NAME)
    return names


def migrate_legacy_config(config_dir: str, legacy_path: str = CONFIG_FILENAME) -> None:
    if os.path.isdir(config_dir) or not os.path.exists(legacy_path):
        return
    os.makedirs(config_dir, exist_ok=True)
    try:
        shutil.move(legacy_path, config_file_path(config_dir, DEFAULT_CONFIG_NAME))
    except OSError as e:
        print(f"Config migration error: {e}")
