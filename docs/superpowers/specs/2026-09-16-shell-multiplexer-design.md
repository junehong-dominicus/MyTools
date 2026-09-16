# Shell Multiplexer — Design Spec

Date: 2026-09-16
Status: Approved for planning

## Summary

A new standalone Windows desktop tool, `shell_multiplexer/`, living alongside the
existing Serial Monitor in the `MyTools` repo. It presents 1-4 fully interactive
PowerShell terminal panes in a single resizable window. Each pane's shell count
and starting directory are user-configurable and persisted across restarts.

## Goals

- Embed 1-4 real, interactive PowerShell sessions in one window.
- Each session must behave like a real terminal: colors, cursor movement,
  tab-completion redraw, `Ctrl+C`, progress bars, works with `git status`
  colorization, etc.
- User picks how many shells (1-4) and each shell's starting directory;
  both are remembered between app launches.
- Follow the conventions already established by the Serial Monitor tool in
  this repo (see "Prior art" below) so the two tools feel like one family.

## Non-goals

- Not a full terminal emulator product (no themes, no tabs-within-panes, no
  SSH, no split-within-a-pane). Just 1-4 fixed panes.
- Not cross-platform. Windows/ConPTY only (matches the rest of this repo).
- No plugin/extension system.

## Prior art in this repo (Serial Monitor, `main.py`)

The new tool deliberately mirrors these existing patterns instead of
inventing new ones:

- `DEFAULT_PANE_COUNT` / `MAX_PANE_COUNT` constants, a toolbar combo box to
  pick count (1-4), and `build_panes(count)` that tears down and rebuilds a
  nested `QSplitter` tree: 1 → single pane, 2 → side-by-side, 3 → 2-over-1,
  4 → 2×2 grid. Prior per-pane settings are captured before teardown and
  reapplied to the new panes by pane id.
- Each pane is a `QFrame` "card" (`SerialPane`) with a fixed-height header
  row holding controls, and a content area below.
- Persistence is a plain JSON file next to the executable
  (`serial_config_v2.json`), loaded automatically on startup and written by
  an explicit "Save Settings" toolbar button — not a settings dialog, not
  `QSettings`.
- `common/ui_theme.py` (vendored, not shared via a path dependency) supplies
  `apply_industrial_theme()` and accent colors.
- Windows taskbar icon fix (`SetCurrentProcessExplicitAppUserModelID`) at
  startup.
- The whole tool is one PyInstaller-built exe via a `.spec` file and a
  `build_exe.py` that copies the result into `exe/`.

## Architecture

### Directory layout

```
MyTools/
  shell_multiplexer/
    main.py
    pty_backend.py
    terminal_screen.py
    input_translator.py
    terminal_widget.py
    shell_pane.py
    common/                 # vendored copy of ui_theme.py + app_icon.ico
    ShellMultiplexer.spec
    build_exe.py
    pyproject.toml          # own deps: PySide6, pywinpty, pyte
    uv.lock
```

It is a sibling standalone tool, not a mode of the existing `main.py`. It
gets its own `pyproject.toml`/lockfile because it needs `pywinpty` and
`pyte`, which the Serial Monitor does not use.

### Components

**`pty_backend.py` — `PtyBackend`**
- Wraps `pywinpty` (`winpty.PtyProcess`). `spawn(cwd)` launches
  `powershell.exe -NoLogo` under a ConPTY with the given working directory
  and an initial size.
- Runs a background `threading.Thread` that blocks on `pty.read()` and
  re-emits each chunk as bytes through a `QObject` signal
  (`output_received(bytes)`), so all Qt-side handling stays on the main
  thread.
- `write(data: bytes)` writes to the pty's stdin.
- `resize(cols, rows)` calls the pty's resize.
- `is_alive()` / `exited` signal: the reader thread treats an empty read or
  a dead process as exit and emits `exited(returncode)`.
- `terminate()` for graceful shutdown (used on pane rebuild and app close).

**`terminal_screen.py` — `TerminalScreen`**
- A thin wrapper pairing a `pyte.HistoryScreen` (grid + scrollback + SGR
  color/attribute state) with a `pyte.ByteStream` feeding it.
- `feed(data: bytes)` decodes and applies to the screen.
- `resize(cols, rows)` resizes the underlying `pyte` screen.
- Exposes the current grid (`display`, per-cell attributes) and cursor
  position for the widget to paint.

**`input_translator.py` — `translate(event: QKeyEvent) -> bytes`**
- Pure function: maps arrow keys, Home/End/PageUp/PageDown, F1-F12,
  Ctrl+C/D/L/etc., Alt-combinations, and plain printable text to the byte
  sequences PowerShell/ConPTY expects.
- No Qt widget or I/O dependency — this is the one piece with real unit
  test value (input → expected bytes table).

**`terminal_widget.py` — `TerminalWidget(QWidget)`**
- Owns one `PtyBackend` + one `TerminalScreen`.
- `paintEvent`: draws the grid cell-by-cell with `QPainter` using a fixed
  monospace font, mapping `pyte` SGR colors to a standard 16-color ANSI
  terminal palette (independent of `ui_theme`'s chrome colors — this is
  terminal *content*, not app chrome). Draws the cursor (blinking via a
  `QTimer`).
- `resizeEvent`: recomputes cols/rows from the widget's pixel size and the
  font's cell metrics, then calls `TerminalScreen.resize()` and
  `PtyBackend.resize()`.
- `keyPressEvent`: `input_translator.translate()` → `PtyBackend.write()`.
- Repaints are coalesced through a short `QTimer` (~30-60fps cap) rather
  than firing on every output chunk, since builds/scripts can burst output
  much faster than the screen needs to redraw.
- On the backend's `exited` signal: stops accepting input and asks its
  parent `ShellPane` to show the exited state.

**`shell_pane.py` — `ShellPane(QFrame)`**
- Same "card" shape as `SerialPane`: header row with pane number, a
  start-path `QLineEdit` + "Browse…" button (native folder picker), and a
  "Restart" button (a pty's cwd can't change after spawn, so changing the
  path requires restarting the shell). `TerminalWidget` fills the body.
- On construction (or Restart), validates the path exists; if not, falls
  back to the user's home directory and shows a small inline warning.
- Spawn failures (e.g. `powershell.exe` missing) are caught and shown
  inline in the pane rather than raised.

**`main.py` — `MainWindow`**
- Toolbar: title, "SHELL COUNT" combo (1-4, default 1), "Save Settings"
  button.
- `build_panes(count)`: same teardown/rebuild + nested-`QSplitter` grid
  algorithm as the Serial Monitor, carrying forward each surviving pane
  id's start path across a count change.
- `load_settings()` / `save_settings()`: JSON file `shell_config.json` next
  to the exe:
  ```json
  {
    "shell_count": 2,
    "panes": {
      "1": {"start_path": "C:\\Projects\\foo"},
      "2": {"start_path": "C:\\Users\\June"}
    }
  }
  ```
  Loaded automatically at startup (invalid/missing → defaults, same
  tolerant `try/except` pattern as the existing tool). Saved only when the
  user clicks "Save Settings".
- `closeEvent`: terminates every pane's `PtyBackend` (and joins its reader
  thread) so no orphaned `powershell.exe` processes survive the app.

## Data flow

1. Pane created/restarted → `PtyBackend.spawn(cwd)`.
2. Reader thread blocks on pty output → emits `output_received(bytes)` on
   the Qt main thread.
3. `TerminalScreen.feed(bytes)` updates the grid/cursor/scrollback.
4. Coalesced timer triggers `TerminalWidget.update()` → `paintEvent` reads
   the current screen state and draws it.
5. Keystrokes: `keyPressEvent` → `input_translator.translate()` →
   `PtyBackend.write()`.
6. Resize: `resizeEvent` → recompute cols/rows → `TerminalScreen.resize()`
   + `PtyBackend.resize()`.
7. Exit: reader thread detects EOF/dead process → `exited` signal →
   `ShellPane` shows exited state + Restart.

## Error handling

- Bad/missing start path: fall back to home directory, inline warning, does
  not block the other panes.
- Spawn failure: caught, shown inline, pane stays usable via Restart.
- Reader-thread exceptions: caught and logged; pane transitions to exited
  state rather than crashing the app.
- Changing shell count: every replaced pane's backend is terminated and its
  reader thread joined *before* the splitter tree is torn down, mirroring
  `toggle_connection()`'s graceful-disconnect-before-teardown pattern.
- App close: all backends terminated so no child processes leak.

## Testing

Terminal-emulation correctness is primarily verified through manual QA
(the interactive behavior doesn't unit-test meaningfully):

- Each shell count (1/2/3/4) renders the correct grid layout.
- Each pane starts in its configured directory (`Get-Location`).
- ANSI colors render correctly (`git status` in a repo with changes,
  `Get-ChildItem`).
- `Ctrl+C` interrupts a running command.
- Resizing the window reflows wrapped output correctly
  (`$Host.UI.RawUI.WindowSize` matches).
- Closing the app leaves no orphaned `powershell.exe` processes (Task
  Manager check).
- Save/reload settings round-trips shell count and start paths.

Real unit tests cover the two pure-function pieces:
- `input_translator.translate()` — key event → expected byte sequence
  table.
- `save_settings()` / `load_settings()` — JSON round-trip, including
  malformed/missing file tolerance.

## Packaging

- New `ShellMultiplexer.spec` (adapted from `MyTools.spec`) and a
  `build_exe.py` copy targeting `ShellMultiplexer.exe`, output copied to
  `exe/` — same flow as the existing tool.
- `pyproject.toml`/`uv.lock` scoped to this subfolder, adding `pywinpty` and
  `pyte` on top of `PySide6`.
- README gets a new section describing the tool, alongside the existing
  Serial Monitor section.

## Open items resolved during brainstorming

- Terminal fidelity: full ConPTY-backed emulation, not a plain
  stdin/stdout console box (approved).
- Rendering approach: custom `QPainter` grid widget over a
  `QPlainTextEdit` full-redraw approach (approved).
- Layout: resizable splitters reusing the Serial Monitor's grid algorithm,
  not tabs or a fixed non-resizable grid (approved).
- Persistence: JSON file + explicit Save button (matching existing tool),
  not a separate modal settings dialog (approved).
- Location: new subfolder within the `MyTools` repo, not a separate repo
  (approved).
