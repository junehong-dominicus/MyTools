# Shell Multiplexer: per-pane command history

Date: 2026-09-18

## Problem

Shell Multiplexer embeds raw PowerShell terminals (ConPTY + pyte). There is
no separate command-input line — the user types directly into the
terminal — and nothing on the app side tracks or persists what was typed.
The user wants a per-pane history of typed commands that also survives
across the named/selectable config files (`configs/*.json`) added
earlier this session.

## Scope

Shell Multiplexer only. Serial Monitor's existing `CommandLineEdit`
in-memory history is out of scope for this change.

## Capture mechanism

Raw keystroke buffering (accumulate characters typed since the last Enter)
was considered and rejected: it would miss anything PowerShell fills in
itself — tab-completion, or recalling a previous command via the Up arrow
through PSReadLine — both of which are common in normal use, and the
resulting history would be misleadingly incomplete.

Instead, capture happens by reading the **rendered screen line** at the
moment Enter is pressed. `TerminalWidget` already renders from a
`TerminalScreen` (pyte-backed) buffer that reflects everything actually
displayed on screen, regardless of how the text got there (typed,
recalled, or completed). This is robust to all of the above.

The captured line includes the shell prompt (e.g.
`PS C:\Users\June> git status`), not just the bare command. Stripping the
prompt was considered and rejected: prompt format varies with cwd and any
custom profile (oh-my-posh, etc.), so stripping would be fragile. Keeping
the full line makes the history read like an audit trail, which is an
acceptable (and arguably more useful) shape for a read-only log.

A captured line is only kept if it is non-empty after stripping trailing
whitespace — pressing Enter on a blank prompt does not add an entry.

**Known limitation — wrapped command lines.** Capture only reads the
cursor's current visual row (`self.screen.get_line_text(self.screen.cursor.y)`).
If a command line wraps across more than one visual row — because the
pane is narrow and the prompt plus typed command together exceed the
pane's column count — only that final visual row is captured; the prompt
and the beginning of the wrapped command are lost from that history entry.
pyte doesn't expose a per-line "this row is a continuation of a wrap"
flag, so there's no cheap, robust way to reconstruct the full logical line
from the rendered buffer alone. This is accepted as a known limitation,
not a bug to chase.

## Storage

`TerminalScreen` (terminal_screen.py) gains:

```python
def get_line_text(self, y: int) -> str:
    """Render row y as plain text (cell data concatenated), right-stripped."""
```

`TerminalWidget` (terminal_widget.py) gains:

- `self._history: list[str] = []` in `__init__`.
- `MAX_HISTORY_ENTRIES = 200` module constant.
- `get_history(self) -> list[str]` — returns a copy of `self._history`.
- `load_history(self, entries: list[str]) -> None` — sets
  `self._history = list(entries)[-MAX_HISTORY_ENTRIES:]`.
- In `keyPressEvent`, when `translate_key_event(event)` returns `"\r"`
  (Enter) and `self.screen is not None`: read
  `line = self.screen.get_line_text(self.screen.cursor.y).strip()`; if
  non-empty, append to `self._history` and trim to the last
  `MAX_HISTORY_ENTRIES`. This read happens before the `"\r"` is written to
  the backend (order doesn't functionally matter — the screen doesn't
  change until output arrives asynchronously from the child process — but
  reading first keeps the capture next to the key that triggered it).

History lives on `TerminalWidget`, not `ShellPane`, mirroring the existing
split where terminal-specific state (font size, screen buffer) lives on
`TerminalWidget` and pane chrome (start path, status label) lives on
`ShellPane`.

## UI

`ShellPane` (shell_pane.py) gains a "History" button in the header row
(after Restart), wired to a new `_show_history` method that opens a
`QDialog` containing a read-only `QListWidget` populated from
`self.terminal.get_history()`, scrolled to the last item on open. No
re-run/replay action — view and copy (via normal list selection + Ctrl+C)
only. The dialog is created fresh each time (not cached), since history
content can change between opens.

## Persistence & carry-forward

`settings.py`:

- `save_settings_file(path, layout_mode, pane_paths, font_size=DEFAULT_FONT_SIZE, pane_histories=None)` —
  `pane_histories: dict[int, list[str]] | None`, defaults to `{}`. Each
  pane's JSON object gains a `"history"` key:
  `{"start_path": ..., "history": pane_histories.get(pid, [])}`.
- `load_settings_file(path) -> tuple[str, dict[int, str], int, dict[int, list[str]]]` —
  now returns a 4-tuple. For each pane entry, `history` is read via
  `pane_cfg.get("history", [])`; if it isn't a list, or any element isn't
  a string, that pane's history falls back to `[]` (defensive, matches
  the existing "never crash on malformed config" convention). Loaded
  history is also capped to the last 200 entries. Configs saved before
  this feature existed have no `"history"` key at all and must default
  to `[]` per pane, not crash — same backward-compatibility contract
  already established for `font_size`.

`main.py` (`MainWindow`):

- `build_panes(self, mode, initial_paths=None, initial_histories=None)` —
  gains `initial_histories`. Mirrors the existing `prior_paths` pattern:
  `prior_histories = {p.pane_id: p.terminal.get_history() for p in self.panes}`,
  then `if initial_histories: prior_histories.update(initial_histories)`.
- `_make_pane(self, pane_id, prior_paths, prior_histories)` — after
  constructing `pane` and before returning, call
  `pane.terminal.load_history(prior_histories.get(pane_id, []))`.
- Constructor, `_write_config`, `_load_config`: thread the 4-tuple/extra
  dict through exactly where `initial_paths`/`pane_paths` already flow
  today (constructor unpacks the 4-tuple from `load_settings_file`;
  `_write_config` gathers `pane_histories = {p.pane_id: p.terminal.get_history() for p in self.panes}`
  before calling `save_settings_file`; `_load_config` unpacks the 4-tuple
  and passes `histories` into `build_panes`).

Net effect: history for pane N survives a SHELL COUNT change (1 → 4 shells
and back) the same way its start path does, and Save/Save As/Load carry
it through the config files exactly like paths and font size.

Captured history can include sensitive values the user typed (e.g. a
command with an API key or credential passed as a CLI argument), and this
is written verbatim into `configs/*.json` on disk. This is mitigated by
`configs/` already being gitignored and this being a local single-user
tool, but is worth being aware of.

## Testing

- `test_terminal_screen.py`: `get_line_text` renders a row's text
  correctly, including trailing-space stripping.
- `test_terminal_widget.py`: pressing Enter with non-empty screen content
  on the cursor row appends to history; blank Enter does not; history
  caps at 200 entries; `load_history` truncates to the last 200 if given
  more.
- `test_settings.py`: `save_settings_file`/`load_settings_file` round-trip
  `pane_histories`; a config missing `"history"` defaults to `[]`; a
  malformed `"history"` value (not a list, or non-string elements) falls
  back to `[]` rather than crashing.
- `test_main_window.py`: history carries forward across `build_panes`
  rebuild keyed by `pane_id`; Save/Save As writes current history into the
  config file; Load restores it into the rebuilt panes.

## Out of scope (YAGNI)

- Re-running a history entry (sending it back to the pty).
- App-level Up/Down recall in the terminal (would conflict with
  PSReadLine's own history, which already works).
- Any UI for editing or clearing history (the "History" button is
  view-only for now).
