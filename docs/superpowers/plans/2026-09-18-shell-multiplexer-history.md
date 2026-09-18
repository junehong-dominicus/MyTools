# Shell Multiplexer Per-Pane Command History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each Shell Multiplexer pane a persistent, per-pane history of typed commands, viewable via a "History" button, that survives layout rebuilds and is saved/restored through the existing named config files.

**Architecture:** `TerminalWidget` captures the rendered screen line at the moment Enter is pressed (not raw keystrokes, so it stays correct across tab-completion and PSReadLine's own Up-arrow recall) and keeps the last 200 entries in memory. `ShellPane` exposes them via a read-only dialog. `settings.py` and `MainWindow` thread the history through the config files exactly the way pane start paths already flow.

**Tech Stack:** Python 3.10+, PySide6, pyte (via the existing `TerminalScreen` wrapper), pytest (offscreen Qt platform).

**Spec:** `docs/superpowers/specs/2026-09-18-shell-multiplexer-history-design.md`

## Global Constraints

- Capture happens by reading the rendered screen line at Enter, not by buffering raw keystrokes (spec §Capture mechanism) — this must stay robust to tab-completion and PSReadLine history recall.
- Captured lines include the shell prompt; the prompt is never stripped (spec §Capture mechanism).
- A line is only recorded if non-empty after `.strip()` — pressing Enter on a blank prompt records nothing.
- History is capped at the last 200 entries (`MAX_HISTORY_ENTRIES = 200`), both when appended live and when loaded from a config file. This constant is defined independently in both `terminal_widget.py` and `settings.py` (deliberately duplicated — `settings.py` has zero Qt/pyte dependencies today and must stay that way).
- History lives on `TerminalWidget`, not `ShellPane` (spec §Storage).
- The "History" dialog is view/copy only — no re-run action, no app-level Up/Down recall, no edit/clear UI (spec §Out of scope).
- All working directory for pytest commands below is `shell_multiplexer/`, using its own venv: `./.venv/Scripts/python.exe -m pytest ...`.

---

### Task 1: `TerminalScreen.get_line_text`

**Files:**
- Modify: `terminal_screen.py`
- Test: `tests/test_terminal_screen.py`

**Interfaces:**
- Produces: `TerminalScreen.get_line_text(self, y: int) -> str` — the row's rendered text, right-stripped of trailing padding.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_terminal_screen.py`:

```python
def test_get_line_text_returns_typed_content():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("hi")
    assert screen.get_line_text(0) == "hi"


def test_get_line_text_strips_trailing_padding():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("hi")
    assert len(screen.get_line_text(0)) == len("hi")


def test_get_line_text_on_second_row():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("ab\r\ncd")
    assert screen.get_line_text(1) == "cd"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_terminal_screen.py -v`
Expected: 3 new FAILs with `AttributeError: 'TerminalScreen' object has no attribute 'get_line_text'`

- [ ] **Step 3: Implement `get_line_text`**

In `terminal_screen.py`, add after `get_cell`:

```python
    def get_line_text(self, y: int) -> str:
        return "".join(self._screen.buffer[y][x].data for x in range(self._screen.columns)).rstrip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_terminal_screen.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add terminal_screen.py tests/test_terminal_screen.py
git commit -m "feat(shell-multiplexer): add TerminalScreen.get_line_text"
```

---

### Task 2: `TerminalWidget` history capture

**Files:**
- Modify: `terminal_widget.py`
- Test: `tests/test_terminal_widget.py`

**Interfaces:**
- Consumes: `TerminalScreen.get_line_text(y: int) -> str` (Task 1).
- Produces: `TerminalWidget.get_history(self) -> list[str]`, `TerminalWidget.load_history(self, entries: list[str]) -> None`, module constant `MAX_HISTORY_ENTRIES = 200`.

- [ ] **Step 1: Write the failing tests**

Add these imports to `tests/test_terminal_widget.py` (extend the existing `from terminal_widget import (...)` block to also pull in `MAX_HISTORY_ENTRIES`):

```python
from terminal_widget import (
    ANSI_BRIGHT_COLORS,
    ANSI_COLORS,
    DEFAULT_FG,
    MAX_HISTORY_ENTRIES,
    _RESIZE_DEBOUNCE_MS,
    TerminalWidget,
    compute_grid_size,
    compute_visible_window,
    resolve_color,
)
```

Append these tests to the end of the file:

```python
def test_enter_with_content_appends_to_history(qapp):
    widget = TerminalWidget()
    widget.screen = TerminalScreen(columns=40, lines=15)
    widget.screen.feed("PS C:\\> git status")

    QTest.keyClick(widget, Qt.Key_Return)

    assert widget.get_history() == ["PS C:\\> git status"]

    widget._blink_timer.stop()


def test_enter_on_blank_line_does_not_append(qapp):
    widget = TerminalWidget()
    widget.screen = TerminalScreen(columns=40, lines=15)

    QTest.keyClick(widget, Qt.Key_Return)

    assert widget.get_history() == []

    widget._blink_timer.stop()


def test_enter_with_no_screen_does_not_crash(qapp):
    widget = TerminalWidget()  # screen is None -- start() never called

    QTest.keyClick(widget, Qt.Key_Return)

    assert widget.get_history() == []

    widget._blink_timer.stop()


def test_load_history_truncates_to_max_entries(qapp):
    widget = TerminalWidget()
    widget.load_history([f"cmd{i}" for i in range(MAX_HISTORY_ENTRIES + 5)])

    history = widget.get_history()

    assert len(history) == MAX_HISTORY_ENTRIES
    assert history[0] == "cmd5"
    assert history[-1] == f"cmd{MAX_HISTORY_ENTRIES + 4}"

    widget._blink_timer.stop()


def test_history_caps_at_max_entries_when_appending(qapp):
    widget = TerminalWidget()
    widget.screen = TerminalScreen(columns=40, lines=15)
    widget.load_history([f"old{i}" for i in range(MAX_HISTORY_ENTRIES)])
    widget.screen.feed("newest")

    QTest.keyClick(widget, Qt.Key_Return)

    history = widget.get_history()

    assert len(history) == MAX_HISTORY_ENTRIES
    assert history[0] == "old1"  # "old0" dropped to make room
    assert history[-1] == "newest"

    widget._blink_timer.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_terminal_widget.py -v`
Expected: FAILs — `ImportError: cannot import name 'MAX_HISTORY_ENTRIES'` (collection error) until Step 3 lands.

- [ ] **Step 3: Implement history capture**

In `terminal_widget.py`, add the module constant after `_RESIZE_DEBOUNCE_MS`:

```python
# How many typed command lines to remember per pane (see keyPressEvent).
# Also duplicated as settings.MAX_HISTORY_ENTRIES for capping on load --
# settings.py has no Qt/pyte dependency and must stay that way.
MAX_HISTORY_ENTRIES = 200
```

In `TerminalWidget.__init__`, add after `self._visible_rows = 24`:

```python
        self._history: list[str] = []
```

Add these methods after `set_font_size`:

```python
    def get_history(self) -> list[str]:
        return list(self._history)

    def load_history(self, entries: list[str]) -> None:
        self._history = list(entries)[-MAX_HISTORY_ENTRIES:]
```

Replace `keyPressEvent`:

```python
    def keyPressEvent(self, event) -> None:
        text = translate_key_event(event)
        if text == "\r" and self.screen is not None:
            line = self.screen.get_line_text(self.screen.cursor.y).strip()
            if line:
                self._history.append(line)
                self._history = self._history[-MAX_HISTORY_ENTRIES:]
        if text:
            self.backend.write(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_terminal_widget.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add terminal_widget.py tests/test_terminal_widget.py
git commit -m "feat(shell-multiplexer): capture per-pane command history on Enter"
```

---

### Task 3: `ShellPane` History button + dialog

**Files:**
- Modify: `shell_pane.py`
- Test: `tests/test_shell_pane.py`

**Interfaces:**
- Consumes: `TerminalWidget.get_history() -> list[str]` (Task 2).
- Produces: `ShellPane._show_history(self) -> None`, a "History" `QPushButton` in the pane header.

- [ ] **Step 1: Write the failing tests**

Add to the top of `tests/test_shell_pane.py`, extending the existing imports:

```python
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QListWidget, QPushButton
```

Append these tests to the end of the file:

```python
def test_show_history_opens_dialog_listing_terminal_history(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["PS C:\\> git status", "PS C:\\> ls"])

    pane._show_history()

    dialogs = pane.findChildren(QDialog)
    assert len(dialogs) == 1
    history_list = dialogs[0].findChild(QListWidget)
    items = [history_list.item(i).text() for i in range(history_list.count())]
    assert items == ["PS C:\\> git status", "PS C:\\> ls"]

    dialogs[0].close()


def test_history_button_click_opens_dialog(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.terminal.load_history(["cmd one"])
    history_btn = next(b for b in pane.findChildren(QPushButton) if b.text() == "History")

    QTest.mouseClick(history_btn, Qt.LeftButton)

    dialogs = pane.findChildren(QDialog)
    assert len(dialogs) == 1

    dialogs[0].close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_shell_pane.py -v`
Expected: 2 new FAILs — `AttributeError: 'ShellPane' object has no attribute '_show_history'` (first test), `StopIteration` from the `next(...)` call finding no "History" button (second test).

- [ ] **Step 3: Implement the History button and dialog**

In `shell_pane.py`, update the import line to add `QDialog` and `QListWidget`:

```python
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QVBoxLayout,
)
```

Add the button after `restart_btn`'s block (still inside `__init__`, before `layout.addWidget(header)`):

```python
        history_btn = QPushButton("History")
        history_btn.clicked.connect(self._show_history)
        header_layout.addWidget(history_btn)
```

Add this method after `_browse`:

```python
    def _show_history(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Shell {self.pane_id} History")
        dialog_layout = QVBoxLayout(dialog)
        history_list = QListWidget()
        history_list.addItems(self.terminal.get_history())
        dialog_layout.addWidget(history_list)
        dialog.resize(500, 400)
        dialog.show()
        history_list.scrollToBottom()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_shell_pane.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add shell_pane.py tests/test_shell_pane.py
git commit -m "feat(shell-multiplexer): add History button and viewer dialog to ShellPane"
```

---

### Task 4: Persist history through `settings.py` and thread it through `MainWindow`

This task touches both `settings.py` (return-shape change) and `main.py` (its only caller) together: splitting them into separate commits would leave the tree failing `test_main_window.py` in between, since `main.py` unpacks `load_settings_file`'s return value directly. Steps stay bite-sized; the commit at the end lands both files atomically.

**Files:**
- Modify: `settings.py`
- Modify: `main.py`
- Test: `tests/test_settings.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `TerminalWidget.get_history()` / `load_history()` (Task 2).
- Produces: `save_settings_file(path, layout_mode, pane_paths, font_size=DEFAULT_FONT_SIZE, pane_histories=None)`, `load_settings_file(path) -> tuple[str, dict[int, str], int, dict[int, list[str]]]`, `MainWindow.build_panes(mode, initial_paths=None, initial_histories=None)`, `MainWindow._make_pane(pane_id, prior_paths, prior_histories)`.

- [ ] **Step 1: Write the failing tests for `settings.py`**

Replace the full contents of `tests/test_settings.py` with:

```python
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


def test_history_is_capped_on_load(tmp_path):
    path = tmp_path / "cfg.json"
    long_history = [f"cmd{i}" for i in range(MAX_HISTORY_ENTRIES + 50)]
    path.write_text(json.dumps({"layout_mode": "1", "panes": {"1": {"start_path": "C:\\a", "history": long_history}}}))

    _, _, _, histories = load_settings_file(str(path))

    assert len(histories[1]) == MAX_HISTORY_ENTRIES
    assert histories[1][-1] == f"cmd{MAX_HISTORY_ENTRIES + 49}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_settings.py -v`
Expected: collection error — `ImportError: cannot import name 'MAX_HISTORY_ENTRIES' from 'settings'`.

- [ ] **Step 3: Implement `pane_histories` in `settings.py`**

Replace the full contents of `settings.py` with:

```python
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
    config = {
        "layout_mode": layout_mode,
        "font_size": font_size,
        "panes": {
            str(pid): {"start_path": p, "history": pane_histories.get(pid, [])}
            for pid, p in pane_paths.items()
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
```

- [ ] **Step 4: Run settings tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_settings.py -v`
Expected: all PASS

- [ ] **Step 5: Write the failing tests for `MainWindow` threading**

Append to `tests/test_main_window.py`:

```python
def test_history_carries_forward_across_rebuild(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_dir=str(tmp_path / "configs"))
    window.panes[0].terminal.load_history(["PS C:\\> git status"])

    window.build_panes("2")

    assert window.panes[0].terminal.get_history() == ["PS C:\\> git status"]


def test_settings_round_trip_across_instances_includes_history(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_dir = str(tmp_path / "configs")

    window = MainWindow(config_dir=config_dir)
    window.panes[0].terminal.load_history(["PS C:\\> ls", "PS C:\\> git status"])
    window.save_current_config()

    window2 = MainWindow(config_dir=config_dir)

    assert window2.panes[0].terminal.get_history() == ["PS C:\\> ls", "PS C:\\> git status"]
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_main_window.py -v`
Expected: at this point `settings.py` already returns a 4-tuple (Step 3 landed) but `main.py` still unpacks 3 values, so ALL of `test_main_window.py` fails to even construct `MainWindow` — `ValueError: too many values to unpack (expected 3)`. This is expected and resolved by the very next step; it is not yet a full commit boundary.

- [ ] **Step 7: Thread history through `MainWindow`**

In `main.py`, update the constructor. Replace:

```python
        migrate_legacy_config(self.config_dir)
        default_path = config_file_path(self.config_dir, DEFAULT_CONFIG_NAME)
        initial_mode, initial_paths, initial_font_size = load_settings_file(default_path)
        self.current_font_size = initial_font_size
```

with:

```python
        migrate_legacy_config(self.config_dir)
        default_path = config_file_path(self.config_dir, DEFAULT_CONFIG_NAME)
        initial_mode, initial_paths, initial_font_size, initial_histories = load_settings_file(default_path)
        self.current_font_size = initial_font_size
```

and replace:

```python
        self.build_panes(initial_mode, initial_paths)
```

with:

```python
        self.build_panes(initial_mode, initial_paths, initial_histories)
```

Replace `build_panes` and `_make_pane`:

```python
    def build_panes(self, mode: str, initial_paths: dict[int, str] | None = None, initial_histories: dict[int, list[str]] | None = None) -> None:
        prior_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        if initial_paths:
            prior_paths.update(initial_paths)

        prior_histories = {p.pane_id: p.terminal.get_history() for p in self.panes}
        if initial_histories:
            prior_histories.update(initial_histories)

        for pane in self.panes:
            pane.terminate()
            pane.setParent(None)
            pane.deleteLater()
        self.panes = []
        self.current_mode = mode

        while self.pane_area_layout.count():
            item = self.pane_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = compute_grid_rows(mode)
        main_splitter = QSplitter(Qt.Vertical)
        for row in rows:
            if len(row) == 1:
                pane = self._make_pane(row[0], prior_paths, prior_histories)
                main_splitter.addWidget(pane)
            else:
                row_splitter = QSplitter(Qt.Horizontal)
                for pane_id in row:
                    pane = self._make_pane(pane_id, prior_paths, prior_histories)
                    row_splitter.addWidget(pane)
                main_splitter.addWidget(row_splitter)

        self.pane_area_layout.addWidget(main_splitter)

    def _make_pane(self, pane_id: int, prior_paths: dict[int, str], prior_histories: dict[int, list[str]]) -> ShellPane:
        path = prior_paths.get(pane_id, os.path.expanduser("~"))
        pane = ShellPane(pane_id, path)
        pane.terminal.set_font_size(self.current_font_size)
        pane.terminal.load_history(prior_histories.get(pane_id, []))
        self.panes.append(pane)
        pane.start_shell()
        return pane
```

Replace `_write_config` and `_load_config`:

```python
    def _write_config(self, name: str) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        pane_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        pane_histories = {p.pane_id: p.terminal.get_history() for p in self.panes}
        save_settings_file(config_file_path(self.config_dir, name), self.current_mode, pane_paths, self.current_font_size, pane_histories)
        self.refresh_config_list(select=name)

    def _load_config(self, name: str) -> None:
        mode, paths, font_size, histories = load_settings_file(config_file_path(self.config_dir, name))
        self.current_font_size = font_size

        self.font_size_combo.blockSignals(True)
        self.font_size_combo.setCurrentText(str(font_size))
        self.font_size_combo.blockSignals(False)

        self.shell_count_combo.blockSignals(True)
        self.shell_count_combo.setCurrentText(mode)
        self.shell_count_combo.blockSignals(False)

        self.build_panes(mode, paths, histories)
```

- [ ] **Step 8: Run the full suite to verify everything passes**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: all tests PASS (this repo's full suite, now including the new history tests).

- [ ] **Step 9: Commit**

```bash
git add settings.py main.py tests/test_settings.py tests/test_main_window.py
git commit -m "feat(shell-multiplexer): persist per-pane history through config files"
```

---

## Plan Self-Review

**Spec coverage:**
- Capture mechanism (screen-line-at-Enter, prompt kept, empty lines skipped) → Task 2, Step 3.
- Storage on `TerminalWidget`, 200-entry cap, `get_history`/`load_history` → Task 2.
- History dialog UI on `ShellPane` → Task 3.
- `settings.py` schema extension + backward compatibility + malformed-value defaulting → Task 4, Steps 1-4.
- `MainWindow` carry-forward across rebuild + Save/Save As/Load threading → Task 4, Steps 5-9.
- Out-of-scope items (re-run, app-level Up/Down, edit/clear UI) → intentionally absent from every task; called out in Global Constraints.

**Placeholder scan:** No TBD/TODO; every step shows complete code, not a description of code.

**Type consistency:** `get_history() -> list[str]` / `load_history(entries: list[str])` (Task 2) match their use in Task 3 (`self.terminal.get_history()`) and Task 4 (`p.terminal.get_history()`, `pane.terminal.load_history(...)`). `load_settings_file`'s 4-tuple order (`mode, paths, font_size, histories`) is consistent across every call site touched in Task 4. `save_settings_file`'s new `pane_histories` parameter is keyword-only in practice (always passed positionally last or by name) and defaults to `None`, so every pre-existing 3-and-4-arg call site in the test suite remains valid unchanged.
