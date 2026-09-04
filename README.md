# MyTools
My tools for Embedded System Developments

## Serial Monitor + Network Scanner

A field technician's Embedded System / Embedded System debug tool: a multi-port serial monitor (originally
migrated from `serial_monitor_v2`), plus network discovery behind a
**Scan** button.

Standalone: vendors its own copy of the shared `common/` theme package, so it has no
dependency on any other repo's directory layout.

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
- `pip install PySide6 pyserial psutil scapy zeroconf requests` (or `uv sync`, using `pyproject.toml`)
- **Windows Administrative Privileges** are required for the ARP portion of Scan (scapy). Without
  elevation, Scan still finds devices via mDNS and HTTP probing, just not raw ARP replies.

### How to Run
```powershell
python main.py
```

### How to Build (EXE)
To generate a standalone Windows executable (built with `uac_admin=True`, so Windows will
prompt for elevation on launch — needed for the ARP scan):
```powershell
python build_exe.py

# Or via PyInstaller directly
python -m PyInstaller MyTools.spec --noconfirm
```
Results will appear in the `dist/` folder, then get copied to `exe/MyTools.exe`.
