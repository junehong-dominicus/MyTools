# Codex adapter for MyTools

AGENTS.md is the Codex-facing adapter beside the Claude layer. Read
[CLAUDE.md](CLAUDE.md) before working on this project: it is the source of truth
for shared architecture, commands, platform constraints, and change conventions.
Read the relevant shared documents as needed rather than maintaining two full
copies of the project instructions.

## Project map

| Path | Purpose |
| --- | --- |
| `serial_monitor/` | Standalone serial monitor and network scanner; `main.py`, `serial_engine.py`, `scanner.py`, `scan_dialog.py` |
| `shell_multiplexer/` | Windows ConPTY / PowerShell terminal app; UI, screen, backend, settings modules and `tests/` |
| `multi_terminal/` | macOS POSIX terminal sibling with its own backend and `tests/` |
| `<app>/common/` | Vendored theme package for each independently buildable app |
| `<app>/pyproject.toml`, `<app>/uv.lock` | App-specific dependencies and locked environment |
| `<app>/build_exe.py`, `<app>/*.spec` | PyInstaller packaging for the corresponding app |
| `docs/superpowers/specs/`, `docs/superpowers/plans/` | Shared feature designs and implementation plans |
| `docs/ui-workflows.md` | Desktop operation contracts and UI test scenarios |
| `README.md` | User-facing installation, launch, and build instructions |
| `CLAUDE.md` | Shared project instruction source |
| `.claude/` | Claude layer; existing local settings and task state remain local |
| `.agents/skills/` | Codex project skills, copied as complete folders from Claude when applicable |
| `.codex/config.toml` | Minimal shared Codex configuration |
| `.codex/agents/` | Codex TOML agent definitions converted from relevant Claude agents |

## Codex workflow

- Run setup and verification from the affected app directory using the commands
  in CLAUDE.md. Keep Windows and macOS backend verification distinct.
- Load relevant `.agents/skills/<name>/SKILL.md` instructions when available.
  Keep supporting files together; do not put project skills in `.codex/skills/`.
- No `.claude/skills/` or `.claude/agents/` sources existed at initial setup,
  so there are currently no copied skills or converted agent definitions.
  The directory README files explain how to add them when sources exist.
- Keep credentials and machine-specific configuration in the user's Codex
  settings or environment, outside the shared project configuration. Ignoring
  `config.local.toml` does not make Codex load it automatically.
- Project configuration is subject to client support, project trust, and managed
  policy. Do not bypass those controls to make this adapter load.

## Keep the adapter aligned

1. Update shared guidance in CLAUDE.md; update this map or Codex-specific notes
   when needed. Avoid copying long sections into both files.
2. When creating or updating a Claude skill that Codex should use, copy its
   entire folder into `.agents/skills/` and review Claude-only tool references.
3. When creating or updating a Claude agent that Codex should spawn, create or
   update the matching `.codex/agents/<name>.toml`; translate the instruction
   body into `developer_instructions` and review runtime/tool differences.
4. Put new shared knowledge in `docs/`, `references/`, or `templates/` and link
   it from both tools. Keep local state and secrets untracked.
