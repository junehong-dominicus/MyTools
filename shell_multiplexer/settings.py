import json
import os

DEFAULT_PANE_COUNT = 1
MAX_PANE_COUNT = 4
CONFIG_FILENAME = "shell_config.json"


def save_settings_file(path: str, shell_count: int, pane_paths: dict[int, str]) -> None:
    config = {
        "shell_count": shell_count,
        "panes": {str(pid): {"start_path": p} for pid, p in pane_paths.items()},
    }
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
    except OSError as e:
        print(f"Save error: {e}")


def load_settings_file(path: str) -> tuple[int, dict[int, str]]:
    if not os.path.exists(path):
        return DEFAULT_PANE_COUNT, {}

    try:
        with open(path, "r") as f:
            config = json.load(f)

        shell_count = config.get("shell_count", DEFAULT_PANE_COUNT)
        if not isinstance(shell_count, int) or not (1 <= shell_count <= MAX_PANE_COUNT):
            shell_count = DEFAULT_PANE_COUNT

        pane_paths = {}
        for pid_str, pane_cfg in config.get("panes", {}).items():
            try:
                pane_paths[int(pid_str)] = pane_cfg.get("start_path", "")
            except (ValueError, AttributeError):
                continue

        return shell_count, pane_paths
    except (json.JSONDecodeError, KeyError, OSError):
        return DEFAULT_PANE_COUNT, {}
