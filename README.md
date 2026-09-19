# MyTools
My tools for Embedded System Developments

## Serial Monitor + Network Scanner

A field technician's Embedded System / Embedded System debug tool: a multi-port serial monitor (originally
migrated from `serial_monitor_v2`), plus network discovery behind a
**Scan** button.

Standalone: lives in `serial_monitor/` and vendors its own copy of the shared `common/`
theme package, so it builds independently of the Shell Multiplexer.

### Features
- **Resizable multi-port serial layout**: Drag and drop proportions between ports (1-4, default 1).
- **Card-Based View**: Each port is isolated in a clean "Card" with a status LED.
- **Log Management**: Consolidated logs in a professional Consolas terminal view.
- **Persistent Settings**: Saves and reloads port count, port, and baud rate configurations
  between sessions.
- **Network Scan**: The **Scan** toolbar button opens a non-modal dialog that discovers
  Embedded System/Embedded System units on the local network (ARP scan + mDNS + HTTP service probing) and lets
  you double-click a result to open its Configuration WebUI. Runs independently of the serial
  panes, so you can scan while a port is connected.

### Prerequisites
- Python 3.10+
- From `serial_monitor/`: `uv sync` (installs `PySide6`, `pyserial`, `psutil`, `scapy`, `zeroconf`, `requests`)
- **Windows Administrative Privileges** are required for the ARP portion of Scan (scapy). Without
  elevation, Scan still finds devices via mDNS and HTTP probing, just not raw ARP replies.

### How to Run
```powershell
cd serial_monitor
python main.py
```

### How to Build
`MyTools.spec` is a single cross-platform PyInstaller spec: it builds whatever OS it's run
on, branching on `sys.platform` for the platform-specific bits (Windows gets
`uac_admin=True` so it prompts for elevation on launch, needed for the ARP scan; macOS
gets a `.app` bundle with no UAC equivalent — ARP scanning there instead requires running
the app with `sudo`, or granting it packet-capture permission).

```powershell
# Windows
cd serial_monitor
python build_exe.py

# Or via PyInstaller directly
python -m PyInstaller MyTools.spec --noconfirm
```
Results appear in `serial_monitor/dist/`, then get copied to `serial_monitor/exe/MyTools.exe`.

```bash
# macOS
cd serial_monitor
uv sync
uv run python build_exe.py
```
Results appear in `serial_monitor/dist/MyTools.app`, then get copied to
`serial_monitor/exe/MyTools.app` (not committed — see `.gitignore`; rebuild locally).

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

Windows-only, by design. The pane backend (`pty_backend.py`) is built
directly on `pywinpty`/ConPTY and spawns `powershell.exe`, so a macOS build
isn't just a new PyInstaller spec — see **MultiTerminal** below, a separate
macOS-native sibling built on this one's design (same panes/layout/settings
UI, `input_translator.py` unchanged) but with a POSIX-pty backend spawning
the user's own login shell instead.

## MultiTerminal

MultiTerminal is Shell Multiplexer's design ported to macOS: the same
resizable 1-4 pane layout, per-pane starting directory, font size, and
saved/loadable configs — but panes are real POSIX ptys running the user's
login shell (`$SHELL -il`, so `.zshrc`/`.zprofile` etc. all load, same as a
normal Terminal.app window) instead of ConPTY + `powershell.exe`.

Standalone: lives in `multi_terminal/` and vendors its own copy of the
`common/` theme package.

### Prerequisites
- macOS
- Python 3.10+
- From `multi_terminal/`: `uv sync` (installs `PySide6`, `pyte` — no pty
  library needed, Python's stdlib `pty`/`termios` module covers it)

### How to Run
```bash
cd multi_terminal
uv run python main.py
```

### How to Build
```bash
cd multi_terminal
uv run python build_exe.py
```
Results appear in `multi_terminal/dist/MultiTerminal.app`, then get copied to
`multi_terminal/exe/MultiTerminal.app` (not committed — see `.gitignore`;
rebuild locally).
