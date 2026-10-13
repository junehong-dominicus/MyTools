# MyTools project instructions

This file is the source of truth for shared project guidance for Claude Code
and Codex. It was created from this checkout's README, package metadata,
source layout, and design documents because no original CLAUDE.md was present.
Codex-specific discovery and setup live in AGENTS.md.

## Project

MyTools contains three standalone Python 3.10+ / PySide6 desktop tools for
embedded development. Each app owns its dependencies, uv.lock, entry point,
build script, and vendored common/ui_theme.py package. Keep them independently
runnable and buildable; do not introduce imports between sibling apps.

- serial_monitor/: serial ports and network discovery (ARP, mDNS, HTTP).
  main.py owns the UI, serial_engine.py handles serial I/O, scanner.py handles
  discovery, and scan_dialog.py provides the scanner UI. Supports Windows and
  macOS. Windows ARP scanning requires administrator privileges; mDNS and HTTP
  discovery can run without elevation. See README.md for platform details.
- shell_multiplexer/: Windows PowerShell terminals using pywinpty / ConPTY.
  Requires Windows 10 1809+ or Windows 11.
- multi_terminal/: macOS terminal sibling using Python POSIX ptys and the
  user's login shell. Its backend imports POSIX-only modules.

For both terminal apps, main.py coordinates windows and configuration;
layout.py arranges panes; shell_pane.py owns pane controls; pty_backend.py
handles shell processes; terminal_screen.py and terminal_widget.py implement
screen state and rendering; input_translator.py translates keyboard input;
settings.py persists configuration. Each has its own tests/ directory.

## Working commands

Run commands from the relevant app directory, not from the repository root:

```text
uv sync
uv run python main.py
uv run python build_exe.py
```

For serial_monitor, shell_multiplexer on Windows, or multi_terminal on macOS:

```text
uv sync --group dev
uv run pytest tests
```

Run each suite separately: the apps use identically named top-level modules.
The test fixtures default Qt to offscreen mode. Validate platform backends on
their supported OS; do not claim macOS backend coverage from Windows.
Serial Monitor tests mock hardware and network I/O. Report live hardware or
network checks separately from these automated tests.
No repository-wide lint or type-check configuration is declared here.

## Change conventions

UI operation contracts and scenarios are documented in docs/ui-workflows.md.

- Follow the surrounding Python and Qt patterns. Preserve the separation
  between UI, terminal screen state, and I/O backends.
- Keep common/ vendored per app. If a theme change applies to multiple apps,
  update the affected copies deliberately, preserving standalone packaging.
- Consult README.md for current run/build behavior, and docs/superpowers/specs/
  and docs/superpowers/plans/ for feature intent. Historical plans may differ
  from the current source; verify implementation before relying on them.
- Preserve backward compatibility and defensive loading in settings files.
  The shell history design is documented in
  docs/superpowers/specs/2026-09-18-shell-multiplexer-history-design.md.
- Builds use each app's build_exe.py and PyInstaller spec, generate dist/,
  and copy deliverables into exe/. Check required specs exist before building.
- Keep generated logs, saved configs, command histories, local overrides,
  environments, and credentials out of git. Histories may contain sensitive
  command arguments. Do not copy local Claude settings or task state into
  shared Codex configuration.

## Maintaining both tools

Update shared project instructions here and keep AGENTS.md as a short adapter.
Copy Codex-relevant Claude skill folders from .claude/skills/ to .agents/skills/
with supporting files intact. Convert relevant .claude/agents/<name>.md files
to .codex/agents/<name>.toml, keeping their behavior in developer_instructions.
Keep shared knowledge in docs/, references/, or templates/ rather than
duplicating long reference material in tool-specific instructions.
