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
