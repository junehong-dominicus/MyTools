# Shell Multiplexer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Windows tool, `shell_multiplexer/`, that embeds 1-4 fully interactive ConPTY-backed PowerShell panes in one resizable window, with per-pane configurable/persisted starting directories.

**Architecture:** A `PtyBackend` (pywinpty ConPTY wrapper) feeds raw text into a `TerminalScreen` (pyte VT emulator); a `TerminalWidget` paints that screen with `QPainter` and forwards translated keystrokes back to the backend. `ShellPane` wraps one `TerminalWidget` with a header (path field, Browse, Restart). `MainWindow` arranges 1-4 `ShellPane`s in the same nested-`QSplitter` grid algorithm the existing Serial Monitor tool uses, and persists shell count + per-pane start paths to a JSON file next to the exe.

**Tech Stack:** Python 3.10+, PySide6, `pywinpty` (ConPTY), `pyte` (VT100/xterm emulation), pytest, PyInstaller.

**Spec:** [docs/superpowers/specs/2026-09-16-shell-multiplexer-design.md](../specs/2026-09-16-shell-multiplexer-design.md)

## Global Constraints

- Windows-only (ConPTY via `pywinpty`); no cross-platform requirement.
- `MAX_PANE_COUNT = 4`, `DEFAULT_PANE_COUNT = 1` (from spec).
- Persistence is a plain JSON file (`shell_config.json`) next to the exe, auto-loaded on startup, written only by an explicit "Save Settings" button — no `QSettings`, no modal settings dialog (from spec/prior art).
- Grid layout: rows of at most 2 pane ids — 1→`[[1]]`, 2→`[[1,2]]`, 3→`[[1,2],[3]]`, 4→`[[1,2],[3,4]]` (from spec/prior art).
- `common/` (theme + icon) is vendored into `shell_multiplexer/common/`, not imported from the repo root's `common/` (from spec).
- New tool lives at `shell_multiplexer/` inside the existing `MyTools` repo, with its own `pyproject.toml` (from spec — it needs `pywinpty`/`pyte`, which the Serial Monitor doesn't use).

---

### Task 1: Project scaffolding

**Files:**
- Create: `shell_multiplexer/common/__init__.py`
- Create: `shell_multiplexer/common/ui_theme.py`
- Create: `shell_multiplexer/common/app_icon.ico` (copy of `common/app_icon.ico`)
- Create: `shell_multiplexer/pyproject.toml`
- Create: `shell_multiplexer/tests/__init__.py`
- Create: `shell_multiplexer/tests/conftest.py`
- Create: `shell_multiplexer/main.py` (minimal placeholder window for this task only — expanded in Task 9)

**Interfaces:**
- Produces: a `qapp` pytest fixture (session-scoped `QApplication`) available to every later test file via `shell_multiplexer/tests/conftest.py`.

- [ ] **Step 1: Vendor the common/ theme package**

Copy the two existing files byte-for-byte:

```bash
mkdir -p shell_multiplexer/common
cp common/ui_theme.py shell_multiplexer/common/ui_theme.py
cp common/app_icon.ico shell_multiplexer/common/app_icon.ico
```

`shell_multiplexer/common/__init__.py`:
```python
# Common UI and utility components for shell_multiplexer (vendored copy)
```

- [ ] **Step 2: Add the subfolder's own pyproject.toml**

`shell_multiplexer/pyproject.toml`:
```toml
[project]
name = "shell-multiplexer"
version = "1.0.0"
description = "Multi-pane embedded PowerShell tool for field technicians"
requires-python = ">=3.10"
dependencies = [
    "PySide6>=6.5",
    "pywinpty>=2.0",
    "pyte>=0.8.1",
    "pyinstaller>=6.5.0",
]

[dependency-groups]
dev = ["pytest>=8.0"]
```

- [ ] **Step 3: Add the shared test fixture**

`shell_multiplexer/tests/conftest.py`:
```python
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

`shell_multiplexer/tests/__init__.py`: empty file.

- [ ] **Step 4: Add a minimal main.py so the app can launch**

`shell_multiplexer/main.py`:
```python
import sys
import os

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QIcon

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from common.ui_theme import apply_industrial_theme

if sys.platform == 'win32':
    import ctypes
    myappid = u'mytools.shell_multiplexer.app'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyTools — Shell Multiplexer")
        self.setMinimumSize(1200, 800)


def main():
    app = QApplication(sys.argv)
    apply_industrial_theme(app)

    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, "app_icon.ico")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "common", "app_icon.ico")

    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write a smoke test proving the app boots**

`shell_multiplexer/tests/test_smoke.py`:
```python
from main import MainWindow


def test_main_window_constructs(qapp):
    window = MainWindow()
    assert window.windowTitle() == "MyTools — Shell Multiplexer"
```

- [ ] **Step 6: Install deps and run the test**

Run:
```bash
cd shell_multiplexer
uv sync
uv run pytest tests/test_smoke.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shell_multiplexer/
git commit -m "feat(shell-multiplexer): scaffold project with vendored theme and smoke test"
```

---

### Task 2: Grid layout algorithm

**Files:**
- Create: `shell_multiplexer/layout.py`
- Test: `shell_multiplexer/tests/test_layout.py`

**Interfaces:**
- Produces: `compute_grid_rows(count: int) -> list[list[int]]`, raises `ValueError` outside `1..4`. Consumed by `main.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_layout.py`:
```python
import pytest

from layout import compute_grid_rows


def test_count_1_is_single_row():
    assert compute_grid_rows(1) == [[1]]


def test_count_2_is_side_by_side():
    assert compute_grid_rows(2) == [[1, 2]]


def test_count_3_is_two_over_one():
    assert compute_grid_rows(3) == [[1, 2], [3]]


def test_count_4_is_two_by_two():
    assert compute_grid_rows(4) == [[1, 2], [3, 4]]


def test_count_out_of_range_raises():
    with pytest.raises(ValueError):
        compute_grid_rows(0)
    with pytest.raises(ValueError):
        compute_grid_rows(5)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_layout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'layout'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/layout.py`:
```python
def compute_grid_rows(count: int) -> list[list[int]]:
    """Group pane ids 1..count into rows of at most 2, matching the
    Serial Monitor's layout: 1->single, 2->side-by-side, 3->2-over-1,
    4->2x2."""
    if not (1 <= count <= 4):
        raise ValueError(f"count must be between 1 and 4, got {count}")

    rows = []
    pane_id = 1
    remaining = count
    while remaining > 0:
        row_size = min(2, remaining)
        rows.append(list(range(pane_id, pane_id + row_size)))
        pane_id += row_size
        remaining -= row_size
    return rows
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_layout.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/layout.py shell_multiplexer/tests/test_layout.py
git commit -m "feat(shell-multiplexer): add grid layout algorithm"
```

---

### Task 3: Settings persistence

**Files:**
- Create: `shell_multiplexer/settings.py`
- Test: `shell_multiplexer/tests/test_settings.py`

**Interfaces:**
- Produces: `DEFAULT_PANE_COUNT = 1`, `MAX_PANE_COUNT = 4`, `CONFIG_FILENAME = "shell_config.json"`, `save_settings_file(path: str, shell_count: int, pane_paths: dict[int, str]) -> None`, `load_settings_file(path: str) -> tuple[int, dict[int, str]]`. Consumed by `main.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_settings.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'settings'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/settings.py`:
```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_settings.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/settings.py shell_multiplexer/tests/test_settings.py
git commit -m "feat(shell-multiplexer): add JSON settings persistence"
```

---

### Task 4: Keyboard-to-terminal input translation

**Files:**
- Create: `shell_multiplexer/input_translator.py`
- Test: `shell_multiplexer/tests/test_input_translator.py`

**Interfaces:**
- Produces: `translate_key_event(event: QKeyEvent) -> str`. Consumed by `terminal_widget.py` (Task 7).

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_input_translator.py`:
```python
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from input_translator import translate_key_event


def make_key_event(key, modifiers=Qt.NoModifier, text=""):
    return QKeyEvent(QEvent.KeyPress, key, modifiers, text)


def test_plain_character_passes_through(qapp):
    event = make_key_event(Qt.Key_A, text="a")
    assert translate_key_event(event) == "a"


def test_up_arrow_maps_to_escape_sequence(qapp):
    event = make_key_event(Qt.Key_Up)
    assert translate_key_event(event) == "\x1b[A"


def test_left_arrow_maps_to_escape_sequence(qapp):
    event = make_key_event(Qt.Key_Left)
    assert translate_key_event(event) == "\x1b[D"


def test_ctrl_c_maps_to_etx(qapp):
    event = make_key_event(Qt.Key_C, modifiers=Qt.ControlModifier)
    assert translate_key_event(event) == "\x03"


def test_ctrl_z_maps_to_0x1a(qapp):
    event = make_key_event(Qt.Key_Z, modifiers=Qt.ControlModifier)
    assert translate_key_event(event) == "\x1a"


def test_enter_maps_to_carriage_return(qapp):
    event = make_key_event(Qt.Key_Return, text="\r")
    assert translate_key_event(event) == "\r"


def test_backspace_maps_to_del(qapp):
    event = make_key_event(Qt.Key_Backspace)
    assert translate_key_event(event) == "\x7f"


def test_f5_maps_to_xterm_sequence(qapp):
    event = make_key_event(Qt.Key_F5)
    assert translate_key_event(event) == "\x1b[15~"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_input_translator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'input_translator'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/input_translator.py`:
```python
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

_ARROW_AND_NAV = {
    Qt.Key_Up: "\x1b[A",
    Qt.Key_Down: "\x1b[B",
    Qt.Key_Right: "\x1b[C",
    Qt.Key_Left: "\x1b[D",
    Qt.Key_Home: "\x1b[H",
    Qt.Key_End: "\x1b[F",
    Qt.Key_Insert: "\x1b[2~",
    Qt.Key_Delete: "\x1b[3~",
    Qt.Key_PageUp: "\x1b[5~",
    Qt.Key_PageDown: "\x1b[6~",
}

_FUNCTION_KEYS = {
    Qt.Key_F1: "\x1bOP",
    Qt.Key_F2: "\x1bOQ",
    Qt.Key_F3: "\x1bOR",
    Qt.Key_F4: "\x1bOS",
    Qt.Key_F5: "\x1b[15~",
    Qt.Key_F6: "\x1b[17~",
    Qt.Key_F7: "\x1b[18~",
    Qt.Key_F8: "\x1b[19~",
    Qt.Key_F9: "\x1b[20~",
    Qt.Key_F10: "\x1b[21~",
    Qt.Key_F11: "\x1b[23~",
    Qt.Key_F12: "\x1b[24~",
}

_SIMPLE_KEYS = {
    Qt.Key_Return: "\r",
    Qt.Key_Enter: "\r",
    Qt.Key_Tab: "\t",
    Qt.Key_Backspace: "\x7f",
    Qt.Key_Escape: "\x1b",
}


def translate_key_event(event: QKeyEvent) -> str:
    """Return the text to write to the pty for this key event ("" if
    nothing should be sent)."""
    key = event.key()
    modifiers = event.modifiers()

    if modifiers & Qt.ControlModifier and Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key - Qt.Key_A + 1)  # Ctrl+A -> 0x01 ... Ctrl+Z -> 0x1a

    if key in _ARROW_AND_NAV:
        return _ARROW_AND_NAV[key]
    if key in _FUNCTION_KEYS:
        return _FUNCTION_KEYS[key]
    if key in _SIMPLE_KEYS:
        return _SIMPLE_KEYS[key]

    return event.text()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_input_translator.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/input_translator.py shell_multiplexer/tests/test_input_translator.py
git commit -m "feat(shell-multiplexer): add keyboard-to-terminal input translation"
```

---

### Task 5: Terminal screen (pyte wrapper)

**Files:**
- Create: `shell_multiplexer/terminal_screen.py`
- Test: `shell_multiplexer/tests/test_terminal_screen.py`

**Interfaces:**
- Produces: `class TerminalScreen` with `__init__(self, columns: int, lines: int, history: int = 2000)`, `feed(self, text: str) -> None`, `resize(self, columns: int, lines: int) -> None`, properties `columns`, `lines`, `cursor` (has `.x`, `.y`, `.hidden`), and `get_cell(self, x: int, y: int)` returning a `pyte` `Char` namedtuple (`.data`, `.fg`, `.bg`, `.bold`, `.reverse`, ...). Consumed by `terminal_widget.py` (Task 7).

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_terminal_screen.py`:
```python
from terminal_screen import TerminalScreen


def test_feed_plain_text_updates_display():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("hi")
    assert screen.get_cell(0, 0).data == "h"
    assert screen.get_cell(1, 0).data == "i"


def test_resize_changes_dimensions():
    screen = TerminalScreen(columns=10, lines=2)
    screen.resize(columns=20, lines=5)
    assert screen.columns == 20
    assert screen.lines == 5


def test_sgr_red_foreground_is_captured():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("\x1b[31mred\x1b[0m")
    assert screen.get_cell(0, 0).fg == "red"


def test_cursor_advances_with_input():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("ab")
    assert screen.cursor.x == 2
    assert screen.cursor.y == 0


def test_carriage_return_and_newline_move_cursor_to_next_line():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("ab\r\ncd")
    assert screen.get_cell(0, 1).data == "c"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_terminal_screen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'terminal_screen'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/terminal_screen.py`:
```python
import pyte


class TerminalScreen:
    def __init__(self, columns: int, lines: int, history: int = 2000):
        self._screen = pyte.HistoryScreen(columns, lines, history=history)
        self._stream = pyte.Stream(self._screen)

    def feed(self, text: str) -> None:
        self._stream.feed(text)

    def resize(self, columns: int, lines: int) -> None:
        self._screen.resize(lines=lines, columns=columns)

    @property
    def columns(self) -> int:
        return self._screen.columns

    @property
    def lines(self) -> int:
        return self._screen.lines

    @property
    def cursor(self):
        return self._screen.cursor

    def get_cell(self, x: int, y: int):
        return self._screen.buffer[y][x]
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_terminal_screen.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/terminal_screen.py shell_multiplexer/tests/test_terminal_screen.py
git commit -m "feat(shell-multiplexer): add pyte-based terminal screen wrapper"
```

---

### Task 6: ConPTY backend

**Files:**
- Create: `shell_multiplexer/pty_backend.py`
- Test: `shell_multiplexer/tests/test_pty_backend.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure `pywinpty` wrapper).
- Produces: `class PtyBackend(QObject)` with signals `output_received = Signal(str)` and `exited = Signal(int)`, and methods `spawn(self, cwd: str, columns: int = 80, lines: int = 24) -> None`, `write(self, text: str) -> None`, `resize(self, columns: int, lines: int) -> None`, `is_alive(self) -> bool`, `terminate(self) -> None`. Consumed by `terminal_widget.py` (Task 7).

**Note:** these tests spawn a real `powershell.exe` and take a few seconds each — this is expected for a Windows ConPTY integration test; there is no meaningful way to fake ConPTY here.

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_pty_backend.py`:
```python
import os
import time

from pty_backend import PtyBackend


def _pump_until(qapp, predicate, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.05)
    return False


def test_spawn_and_echo(qapp, tmp_path):
    backend = PtyBackend()
    received = []
    backend.output_received.connect(received.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    backend.write("Write-Output HELLO_MARKER\r")

    found = _pump_until(qapp, lambda: any("HELLO_MARKER" in chunk for chunk in received))

    assert found
    backend.terminate()


def test_is_alive_true_after_spawn(qapp, tmp_path):
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)

    assert backend.is_alive()

    backend.terminate()


def test_exited_signal_fires_on_shell_exit(qapp, tmp_path):
    backend = PtyBackend()
    exited_codes = []
    backend.exited.connect(exited_codes.append)

    backend.spawn(str(tmp_path), columns=80, lines=24)
    backend.write("exit\r")

    found = _pump_until(qapp, lambda: len(exited_codes) > 0)

    assert found


def test_resize_does_not_raise(qapp, tmp_path):
    backend = PtyBackend()
    backend.spawn(str(tmp_path), columns=80, lines=24)

    backend.resize(120, 40)  # should not raise

    backend.terminate()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_pty_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pty_backend'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/pty_backend.py`:
```python
import threading

from PySide6.QtCore import QObject, Signal
from winpty import PtyProcess


class PtyBackend(QObject):
    output_received = Signal(str)
    exited = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._thread = None
        self._stop = False

    def spawn(self, cwd: str, columns: int = 80, lines: int = 24) -> None:
        self._proc = PtyProcess.spawn(
            ["powershell.exe", "-NoLogo"],
            cwd=cwd,
            dimensions=(lines, columns),
        )
        self._stop = False
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while not self._stop:
            try:
                data = self._proc.read(4096)
            except EOFError:
                break
            except Exception:
                break
            if data:
                self.output_received.emit(data)

        code = self._proc.exitstatus if self._proc.exitstatus is not None else -1
        self.exited.emit(code)

    def write(self, text: str) -> None:
        if self._proc and self._proc.isalive():
            self._proc.write(text)

    def resize(self, columns: int, lines: int) -> None:
        if self._proc and self._proc.isalive():
            self._proc.setwinsize(lines, columns)

    def is_alive(self) -> bool:
        return bool(self._proc and self._proc.isalive())

    def terminate(self) -> None:
        self._stop = True
        if self._proc:
            self._proc.terminate(force=True)
        if self._thread:
            self._thread.join(timeout=2)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_pty_backend.py -v`
Expected: PASS (4 tests; each takes a few seconds).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/pty_backend.py shell_multiplexer/tests/test_pty_backend.py
git commit -m "feat(shell-multiplexer): add ConPTY backend wrapping pywinpty"
```

---

### Task 7: Terminal widget (rendering + input + resize)

**Files:**
- Create: `shell_multiplexer/terminal_widget.py`
- Test: `shell_multiplexer/tests/test_terminal_widget.py`

**Interfaces:**
- Consumes: `PtyBackend` (Task 6), `TerminalScreen` (Task 5), `translate_key_event` (Task 4).
- Produces: pure functions `compute_grid_size(widget_width: int, widget_height: int, cell_width: int, cell_height: int) -> tuple[int, int]` and `resolve_color(name, bold: bool, is_fg: bool) -> QColor`; `class TerminalWidget(QWidget)` with signal `exited = Signal(int)` and method `start(self, cwd: str) -> None`. `.backend` (a `PtyBackend`) and `.screen` (a `TerminalScreen` or `None` before `start()`) are public attributes. Consumed by `shell_pane.py` (Task 8).

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_terminal_widget.py`:
```python
from PySide6.QtGui import QColor

from terminal_screen import TerminalScreen
from terminal_widget import (
    ANSI_BRIGHT_COLORS,
    ANSI_COLORS,
    DEFAULT_FG,
    TerminalWidget,
    compute_grid_size,
    resolve_color,
)


def test_compute_grid_size_basic():
    assert compute_grid_size(800, 600, 10, 20) == (80, 30)


def test_compute_grid_size_clamps_to_at_least_one():
    assert compute_grid_size(5, 5, 10, 20) == (1, 1)


def test_resolve_color_default_fg():
    assert resolve_color("default", bold=False, is_fg=True) == QColor(DEFAULT_FG)


def test_resolve_color_named():
    assert resolve_color("red", bold=False, is_fg=True) == QColor(ANSI_COLORS["red"])


def test_resolve_color_bold_uses_bright_variant():
    assert resolve_color("red", bold=True, is_fg=True) == QColor(ANSI_BRIGHT_COLORS["red"])


def test_resolve_color_hex_passthrough():
    assert resolve_color("#112233", bold=False, is_fg=True) == QColor("#112233")


def test_widget_renders_fed_screen_without_error(qapp):
    widget = TerminalWidget()
    widget.resize(400, 300)
    widget.screen = TerminalScreen(columns=40, lines=15)
    widget.screen.feed("hello")

    pixmap = widget.grab()

    assert pixmap.width() == 400
    assert pixmap.height() == 300
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_terminal_widget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'terminal_widget'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/terminal_widget.py`:
```python
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from input_translator import translate_key_event
from pty_backend import PtyBackend
from terminal_screen import TerminalScreen

ANSI_COLORS = {
    "black": "#000000", "red": "#cd3131", "green": "#0dbc79",
    "brown": "#e5e510", "yellow": "#e5e510", "blue": "#2472c8",
    "magenta": "#bc3fbc", "cyan": "#11a8cd", "white": "#e5e5e5",
}

ANSI_BRIGHT_COLORS = {
    "black": "#666666", "red": "#f14c4c", "green": "#23d18b",
    "brown": "#f5f543", "yellow": "#f5f543", "blue": "#3b8eea",
    "magenta": "#d670d6", "cyan": "#29b8db", "white": "#e5e5e5",
}

DEFAULT_FG = "#d4d4d4"
DEFAULT_BG = "#1e1e1e"


def compute_grid_size(widget_width: int, widget_height: int, cell_width: int, cell_height: int) -> tuple[int, int]:
    cols = max(1, widget_width // cell_width)
    rows = max(1, widget_height // cell_height)
    return cols, rows


def resolve_color(name, bold: bool, is_fg: bool) -> QColor:
    if name in (None, "default"):
        return QColor(DEFAULT_FG if is_fg else DEFAULT_BG)
    if isinstance(name, str) and name.startswith("#"):
        return QColor(name)
    if isinstance(name, str) and name.isdigit():
        return QColor(DEFAULT_FG if is_fg else DEFAULT_BG)  # 256-color: out of scope, fall back

    palette = ANSI_BRIGHT_COLORS if (bold and is_fg) else ANSI_COLORS
    hexval = palette.get(name)
    return QColor(hexval if hexval else (DEFAULT_FG if is_fg else DEFAULT_BG))


class TerminalWidget(QWidget):
    exited = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend = PtyBackend(self)
        self.screen: TerminalScreen | None = None
        self._font = QFont("Consolas", 10)

        self.backend.output_received.connect(self._on_output)
        self.backend.exited.connect(self._on_exited)

        self._dirty = False
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(33)
        self._repaint_timer.timeout.connect(self._flush_repaint)

        self._cursor_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._toggle_cursor)
        self._blink_timer.start()

        self.setFocusPolicy(Qt.StrongFocus)

    def _cell_size(self) -> tuple[int, int]:
        metrics = QFontMetrics(self._font)
        return metrics.horizontalAdvance("W"), metrics.height()

    def start(self, cwd: str) -> None:
        cell_w, cell_h = self._cell_size()
        cols, rows = compute_grid_size(self.width(), self.height(), cell_w, cell_h)
        self.screen = TerminalScreen(columns=cols, lines=rows)
        self.backend.spawn(cwd, columns=cols, lines=rows)
        self._repaint_timer.start()

    def _on_output(self, text: str) -> None:
        if self.screen:
            self.screen.feed(text)
            self._dirty = True

    def _flush_repaint(self) -> None:
        if self._dirty:
            self._dirty = False
            self.update()

    def _toggle_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.update()

    def _on_exited(self, code: int) -> None:
        self._repaint_timer.stop()
        self.exited.emit(code)

    def resizeEvent(self, event) -> None:
        if self.screen:
            cell_w, cell_h = self._cell_size()
            cols, rows = compute_grid_size(self.width(), self.height(), cell_w, cell_h)
            self.screen.resize(columns=cols, lines=rows)
            self.backend.resize(cols, rows)
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        text = translate_key_event(event)
        if text:
            self.backend.write(text)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(DEFAULT_BG))

        if self.screen is None:
            painter.end()
            return

        painter.setFont(self._font)
        cell_w, cell_h = self._cell_size()
        ascent = QFontMetrics(self._font).ascent()

        for y in range(self.screen.lines):
            for x in range(self.screen.columns):
                cell = self.screen.get_cell(x, y)
                fg, bg = cell.fg, cell.bg
                if cell.reverse:
                    fg, bg = bg, fg
                if bg not in (None, "default"):
                    painter.fillRect(x * cell_w, y * cell_h, cell_w, cell_h, resolve_color(bg, cell.bold, is_fg=False))
                if cell.data != " ":
                    painter.setPen(resolve_color(fg, cell.bold, is_fg=True))
                    painter.drawText(x * cell_w, y * cell_h + ascent, cell.data)

        cursor = self.screen.cursor
        if not cursor.hidden and self._cursor_visible:
            painter.fillRect(cursor.x * cell_w, cursor.y * cell_h, cell_w, cell_h, QColor(255, 255, 255, 120))

        painter.end()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_terminal_widget.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/terminal_widget.py shell_multiplexer/tests/test_terminal_widget.py
git commit -m "feat(shell-multiplexer): add terminal widget rendering and input handling"
```

---

### Task 8: Shell pane (card widget)

**Files:**
- Create: `shell_multiplexer/shell_pane.py`
- Test: `shell_multiplexer/tests/test_shell_pane.py`

**Interfaces:**
- Consumes: `TerminalWidget` (Task 7).
- Produces: `class ShellPane(QFrame)` with `__init__(self, pane_id: int, start_path: str, parent=None)`, public attributes `pane_id`, `path_edit` (`QLineEdit`), `status_label` (`QLabel`), `terminal` (`TerminalWidget`), and methods `start_shell(self) -> None`, `terminate(self) -> None`. Note: the constructor does **not** auto-start the shell — the caller (`MainWindow`, Task 9) calls `start_shell()` once, after settings are merged in, so a shell isn't spawned twice on startup. Consumed by `main.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_shell_pane.py`:
```python
import os

from shell_pane import ShellPane
from terminal_widget import TerminalWidget


def test_pane_falls_back_to_home_dir_when_path_missing(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, str(tmp_path / "does_not_exist"))

    pane.start_shell()

    assert pane.path_edit.text() == os.path.expanduser("~")


def test_pane_shows_status_on_spawn_failure(qapp, monkeypatch):
    def boom(self, cwd):
        raise RuntimeError("no powershell.exe")

    monkeypatch.setattr(TerminalWidget, "start", boom)
    pane = ShellPane(1, os.path.expanduser("~"))

    pane.start_shell()

    assert "Failed to start shell" in pane.status_label.text()


def test_exit_signal_updates_status(qapp, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, os.path.expanduser("~"))
    pane.start_shell()

    pane.terminal.exited.emit(0)

    assert "exited" in pane.status_label.text().lower()


def test_valid_path_is_kept_as_is(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(TerminalWidget, "start", lambda self, cwd: None)
    pane = ShellPane(1, str(tmp_path))

    pane.start_shell()

    assert pane.path_edit.text() == str(tmp_path)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_shell_pane.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shell_pane'`.

- [ ] **Step 3: Implement**

`shell_multiplexer/shell_pane.py`:
```python
import os

from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from terminal_widget import TerminalWidget


class ShellPane(QFrame):
    def __init__(self, pane_id: int, start_path: str, parent=None):
        super().__init__(parent)
        self.pane_id = pane_id
        self.setObjectName("ShellPane")
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QFrame()
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)

        header_layout.addWidget(QLabel(f"SHELL {pane_id}"))

        self.path_edit = QLineEdit(start_path)
        header_layout.addWidget(self.path_edit, 2)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        header_layout.addWidget(browse_btn)

        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self.start_shell)
        header_layout.addWidget(restart_btn)

        layout.addWidget(header)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.terminal = TerminalWidget()
        self.terminal.exited.connect(self._on_shell_exited)
        layout.addWidget(self.terminal, 1)

    def start_shell(self) -> None:
        path = self.path_edit.text().strip() or os.path.expanduser("~")
        if not os.path.isdir(path):
            path = os.path.expanduser("~")
            self.path_edit.setText(path)
            self.status_label.setText("Path not found — using home directory")
        else:
            self.status_label.setText("")

        try:
            self.terminal.start(path)
        except Exception as e:
            self.status_label.setText(f"Failed to start shell: {e}")

    def _on_shell_exited(self, code: int) -> None:
        self.status_label.setText(f"Shell exited (code {code}) — click Restart")

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select start directory", self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)

    def terminate(self) -> None:
        self.terminal.backend.terminate()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_shell_pane.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/shell_pane.py shell_multiplexer/tests/test_shell_pane.py
git commit -m "feat(shell-multiplexer): add ShellPane card widget"
```

---

### Task 9: MainWindow (toolbar, grid wiring, persistence, shutdown)

**Files:**
- Modify: `shell_multiplexer/main.py` (replace the Task 1 placeholder `MainWindow`)
- Test: `shell_multiplexer/tests/test_main_window.py`

**Interfaces:**
- Consumes: `compute_grid_rows` (Task 2), `DEFAULT_PANE_COUNT`/`MAX_PANE_COUNT`/`CONFIG_FILENAME`/`save_settings_file`/`load_settings_file` (Task 3), `ShellPane` (Task 8).
- Produces: `class MainWindow(QMainWindow)` with `__init__(self, config_path: str = CONFIG_FILENAME)`, public attribute `panes: list[ShellPane]`, methods `build_panes(self, count: int, initial_paths: dict[int, str] | None = None) -> None`, `save_settings(self) -> None`.

- [ ] **Step 1: Write the failing tests**

`shell_multiplexer/tests/test_main_window.py`:
```python
from main import MainWindow
from settings import DEFAULT_PANE_COUNT
from shell_pane import ShellPane


def test_starts_with_default_pane_count(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))

    assert len(window.panes) == DEFAULT_PANE_COUNT


def test_build_panes_creates_correct_count_and_ids(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))

    window.build_panes(4)

    assert len(window.panes) == 4
    assert sorted(p.pane_id for p in window.panes) == [1, 2, 3, 4]


def test_build_panes_carries_forward_paths(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))
    window.panes[0].path_edit.setText("C:\\Kept")

    window.build_panes(2)

    assert window.panes[0].path_edit.text() == "C:\\Kept"


def test_settings_round_trip_across_instances(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    config_path = str(tmp_path / "cfg.json")

    window = MainWindow(config_path=config_path)
    window.build_panes(2)
    window.panes[0].path_edit.setText("C:\\Somewhere")
    window.save_settings()

    window2 = MainWindow(config_path=config_path)

    assert len(window2.panes) == 2
    assert window2.panes[0].path_edit.text() == "C:\\Somewhere"


def test_close_event_terminates_all_panes(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ShellPane, "start_shell", lambda self: None)
    terminated = []
    monkeypatch.setattr(ShellPane, "terminate", lambda self: terminated.append(self.pane_id))
    window = MainWindow(config_path=str(tmp_path / "cfg.json"))
    window.build_panes(3)

    window.close()

    assert sorted(terminated) == [1, 2, 3]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd shell_multiplexer && uv run pytest tests/test_main_window.py -v`
Expected: FAIL — `MainWindow` doesn't yet accept `config_path`, has no `build_panes`/`save_settings`/`panes`.

- [ ] **Step 3: Implement**

Replace the placeholder `MainWindow` and `main()` in `shell_multiplexer/main.py` with:

```python
import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from common.ui_theme import apply_industrial_theme

from layout import compute_grid_rows
from settings import CONFIG_FILENAME, MAX_PANE_COUNT, DEFAULT_PANE_COUNT, load_settings_file, save_settings_file
from shell_pane import ShellPane

if sys.platform == 'win32':
    import ctypes
    myappid = u'mytools.shell_multiplexer.app'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class MainWindow(QMainWindow):
    def __init__(self, config_path: str = CONFIG_FILENAME):
        super().__init__()
        self.config_path = config_path
        self.setWindowTitle("MyTools — Shell Multiplexer")
        self.setMinimumSize(1200, 800)

        self.panes: list[ShellPane] = []
        self.pane_area_layout = None

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)

        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        t_layout = QHBoxLayout(toolbar)

        title = QLabel("MYTOOLS — SHELL MULTIPLEXER")
        title.setStyleSheet("color: #3498DB; font-size: 18px; font-weight: bold;")
        t_layout.addWidget(title)
        t_layout.addStretch()

        t_layout.addWidget(QLabel("SHELL COUNT:"))
        self.shell_count_combo = QComboBox()
        self.shell_count_combo.addItems([str(n) for n in range(1, MAX_PANE_COUNT + 1)])
        self.shell_count_combo.setFixedWidth(60)
        t_layout.addWidget(self.shell_count_combo)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        t_layout.addWidget(save_btn)

        outer_layout.addWidget(toolbar)

        self.pane_area = QWidget()
        self.pane_area_layout = QVBoxLayout(self.pane_area)
        self.pane_area_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.pane_area)

        initial_count, initial_paths = load_settings_file(self.config_path)
        self.shell_count_combo.blockSignals(True)
        self.shell_count_combo.setCurrentText(str(initial_count))
        self.shell_count_combo.blockSignals(False)
        self.shell_count_combo.currentTextChanged.connect(self._on_shell_count_changed)

        self.build_panes(initial_count, initial_paths)

    def build_panes(self, count: int, initial_paths: dict[int, str] | None = None) -> None:
        prior_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        if initial_paths:
            prior_paths.update(initial_paths)

        for pane in self.panes:
            pane.terminate()
            pane.setParent(None)
            pane.deleteLater()
        self.panes = []

        while self.pane_area_layout.count():
            item = self.pane_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = compute_grid_rows(count)
        main_splitter = QSplitter(Qt.Vertical)
        for row in rows:
            if len(row) == 1:
                pane = self._make_pane(row[0], prior_paths)
                main_splitter.addWidget(pane)
            else:
                row_splitter = QSplitter(Qt.Horizontal)
                for pane_id in row:
                    pane = self._make_pane(pane_id, prior_paths)
                    row_splitter.addWidget(pane)
                main_splitter.addWidget(row_splitter)

        self.pane_area_layout.addWidget(main_splitter)

    def _make_pane(self, pane_id: int, prior_paths: dict[int, str]) -> ShellPane:
        path = prior_paths.get(pane_id, os.path.expanduser("~"))
        pane = ShellPane(pane_id, path)
        self.panes.append(pane)
        pane.start_shell()
        return pane

    def _on_shell_count_changed(self, text: str) -> None:
        self.build_panes(int(text))

    def save_settings(self) -> None:
        pane_paths = {p.pane_id: p.path_edit.text() for p in self.panes}
        save_settings_file(self.config_path, len(self.panes), pane_paths)

    def closeEvent(self, event) -> None:
        for pane in self.panes:
            pane.terminate()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    apply_industrial_theme(app)

    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, "app_icon.ico")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "common", "app_icon.ico")

    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd shell_multiplexer && uv run pytest tests/test_main_window.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full test suite**

Run: `cd shell_multiplexer && uv run pytest -v`
Expected: PASS (all tests from Tasks 2-9; Task 6's pty tests each take a few seconds).

- [ ] **Step 6: Commit**

```bash
git add shell_multiplexer/main.py shell_multiplexer/tests/test_main_window.py
git commit -m "feat(shell-multiplexer): wire up MainWindow toolbar, grid, and persistence"
```

---

### Task 10: Packaging

**Files:**
- Create: `shell_multiplexer/ShellMultiplexer.spec`
- Create: `shell_multiplexer/build_exe.py`
- Modify: `README.md` (append a new section)

**Interfaces:** none (build-only task).

- [ ] **Step 1: Add the PyInstaller spec**

`shell_multiplexer/ShellMultiplexer.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Shell Multiplexer tool.
#
# Build:
#   python build_exe.py
#   # or directly:
#   python -m PyInstaller ShellMultiplexer.spec --noconfirm
#
# Produces a single windowed (no-console) exe: dist/ShellMultiplexer.exe
# (build_exe.py then copies it to exe/).

import os

COMMON_ROOT = os.path.abspath(SPECPATH)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[COMMON_ROOT],
    binaries=[],
    datas=[('common/app_icon.ico', 'common')],
    hiddenimports=['common.ui_theme'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ShellMultiplexer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='common/app_icon.ico',
    uac_admin=False,
)
```

- [ ] **Step 2: Add the build script**

`shell_multiplexer/build_exe.py`:
```python
import subprocess
import sys
import os
import shutil


def build_exe():
    print("--- Starting Shell Multiplexer Build ---")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working dir: {script_dir}")

    try:
        import PyInstaller
        print(f"Found PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Error: PyInstaller not found. Please run 'pip install pyinstaller'")
        return

    spec_file = "ShellMultiplexer.spec"
    if not os.path.exists(spec_file):
        print(f"Error: {spec_file} not found in the current directory.")
        return

    cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"]
    print(f"Executing: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print("\n" + "=" * 40)
        print("Success! Standalone EXE is in the 'dist' folder.")
        print("=" * 40)

        exe_name = "ShellMultiplexer.exe"
        src_path = os.path.join('dist', exe_name)
        dest_folder = 'exe'
        dest_path = os.path.join(dest_folder, exe_name)

        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        if os.path.exists(src_path):
            print(f"Copying {exe_name} to {dest_folder}...")
            shutil.copy2(src_path, dest_path)
            print("Copy complete.")
        else:
            print(f"Error: {src_path} not found.")

    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code: {e.returncode}")


if __name__ == "__main__":
    build_exe()
```

- [ ] **Step 3: Document the tool in the root README**

Append to `README.md`:
```markdown

## Shell Multiplexer

A companion field tool: 1-4 fully interactive PowerShell panes (real ConPTY
terminals — colors, cursor movement, `Ctrl+C`, etc.) in one resizable
window, each with its own configurable starting directory.

Standalone: lives in `shell_multiplexer/` and vendors its own copy of the
`common/` theme package, so it builds independently of the Serial Monitor.

### Prerequisites
- Windows 10 1809+ (ConPTY) or Windows 11
- Python 3.10+
- From `shell_multiplexer/`: `uv sync` (installs `PySide6`, `pywinpty`, `pyte`)

### How to Run
```powershell
cd shell_multiplexer
python main.py
```

### How to Build (EXE)
```powershell
cd shell_multiplexer
python build_exe.py
```
Results appear in `shell_multiplexer/dist/`, then get copied to
`shell_multiplexer/exe/ShellMultiplexer.exe`.
```

- [ ] **Step 4: Build and smoke-test the exe**

Run:
```bash
cd shell_multiplexer
uv run python build_exe.py
```
Expected: build succeeds, `exe/ShellMultiplexer.exe` exists. Launch it manually and confirm the window opens with one shell pane running PowerShell.

- [ ] **Step 5: Commit**

```bash
git add shell_multiplexer/ShellMultiplexer.spec shell_multiplexer/build_exe.py README.md
git commit -m "feat(shell-multiplexer): add PyInstaller packaging and README section"
```

---

### Task 11: Manual QA pass

**Files:** none — this task only runs the built (or `python main.py`-launched) app.

- [ ] **Step 1: Verify each shell count renders the correct grid**

Launch the app. For SHELL COUNT = 1, 2, 3, 4 in turn, confirm the layout matches: 1 = full window, 2 = side-by-side, 3 = two-over-one, 4 = 2×2 — matching `compute_grid_rows`.

- [ ] **Step 2: Verify starting directories**

For a 2-shell layout, set pane 1's path to `C:\Windows` and pane 2's to your user profile via Browse, click Restart on each, and run `Get-Location` in both — confirm they differ and match what was set.

- [ ] **Step 3: Verify color rendering and interactivity**

In a pane started inside a git repo with uncommitted changes, run `git status` and confirm colored output renders. Run a long-running command (e.g. `ping -t localhost`) and press `Ctrl+C` — confirm it stops.

- [ ] **Step 4: Verify resize reflow**

Resize the main window (and drag a splitter between two panes). Run `$Host.UI.RawUI.WindowSize` in a pane before and after — confirm the reported size changed to match the new pane dimensions.

- [ ] **Step 5: Verify settings persistence**

Set distinct paths per pane, click "Save Settings", close the app, relaunch it — confirm shell count and per-pane paths were restored.

- [ ] **Step 6: Verify clean shutdown**

With 2+ shells running, close the app. Open Task Manager and confirm no `powershell.exe` processes are left running from this session.

- [ ] **Step 7: Record results**

If all checks pass, no code changes are needed — this task exists to catch anything the automated tests can't (real ConPTY rendering fidelity, real process cleanup). If any check fails, file it as a bug against the specific task/component above and fix before considering the tool done.
