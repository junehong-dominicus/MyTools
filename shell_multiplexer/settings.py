import json
import os

from layout import LAYOUT_MODES

DEFAULT_LAYOUT_MODE = "1"
FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18]
DEFAULT_FONT_SIZE = 10
CONFIG_FILENAME = "shell_config.json"


def save_settings_file(path: str, layout_mode: str, pane_paths: dict[int, str], font_size: int = DEFAULT_FONT_SIZE) -> None:
    config = {
        "layout_mode": layout_mode,
        "font_size": font_size,
        "panes": {str(pid): {"start_path": p} for pid, p in pane_paths.items()},
    }
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
    except OSError as e:
        print(f"Save error: {e}")


def load_settings_file(path: str) -> tuple[str, dict[int, str], int]:
    if not os.path.exists(path):
        return DEFAULT_LAYOUT_MODE, {}, DEFAULT_FONT_SIZE

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
        for pid_str, pane_cfg in config.get("panes", {}).items():
            try:
                pane_paths[int(pid_str)] = pane_cfg.get("start_path", "")
            except (ValueError, AttributeError):
                continue

        return layout_mode, pane_paths, font_size
    except (json.JSONDecodeError, KeyError, OSError, AttributeError, TypeError):
        # AttributeError/TypeError cover valid-JSON-but-wrong-shape configs
        # (e.g. top-level "[]" or "null", or "panes" being a list instead of
        # a dict) where .get()/.items() gets called on something that isn't
        # a dict -- these must fall back to defaults just like malformed
        # JSON, not crash the whole app at startup.
        return DEFAULT_LAYOUT_MODE, {}, DEFAULT_FONT_SIZE
