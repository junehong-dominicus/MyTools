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

from PyInstaller.utils.hooks import collect_all

COMMON_ROOT = os.path.abspath(SPECPATH)

block_cipher = None

# pywinpty's `winpty` package ships native helper binaries (OpenConsole.exe,
# winpty-agent.exe, winpty.dll, conpty.dll) that it spawns/loads at runtime
# from a directory next to its own module. PyInstaller's automatic binary
# scan only follows the PE import table of winpty's compiled extension
# (_winpty.pyd), so it picks up conpty.dll/winpty.dll but has no way to know
# about the helper .exe files that get launched as child processes rather
# than linked as DLLs. Without them, ConPTY/WinPTY initialization fails
# immediately in the frozen build (no real powershell.exe ever attaches),
# even though the same code works fine when run from source. collect_all()
# pulls in everything winpty needs (data files, dynamic libs, submodules).
winpty_datas, winpty_binaries, winpty_hiddenimports = collect_all('winpty')

a = Analysis(
    ['main.py'],
    pathex=[COMMON_ROOT],
    binaries=winpty_binaries,
    datas=[('common/app_icon.ico', 'common')] + winpty_datas,
    hiddenimports=['common.ui_theme'] + winpty_hiddenimports,
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
