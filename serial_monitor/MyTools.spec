# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for MyTools (Orex-i / Faro-i field tool: serial monitor
# + network scanner).
#
# Build:
#   python build_exe.py
#   # or directly:
#   python -m PyInstaller MyTools.spec --noconfirm
#
# Produces a single windowed (no-console) exe: dist/MyTools.exe
# (build_exe.py then copies it to exe/). Runs elevated (uac_admin=True) —
# required for scapy's ARP scan.

import os

# MyTools' own directory (common/ is vendored locally here), so
# `from common.ui_theme import ...` resolves and gets bundled.
COMMON_ROOT = os.path.abspath(SPECPATH)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[COMMON_ROOT],
    binaries=[],
    datas=[('app_icon.ico', '.')],   # main.py loads this from sys._MEIPASS at runtime
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
    name='MyTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # --windowed: GUI app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
    uac_admin=True,              # required for scapy ARP scanning on Windows
)
