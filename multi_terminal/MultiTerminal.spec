# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for MultiTerminal (macOS-only: a real POSIX pty + the
# user's login shell, unlike Shell Multiplexer's ConPTY/PowerShell).
#
# Build:
#   python build_exe.py
#   # or directly:
#   python -m PyInstaller MultiTerminal.spec --noconfirm
#
# Produces dist/MultiTerminal.app (build_exe.py then copies it to exe/).

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('common', 'common')],
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
    [],
    exclude_binaries=True,
    name='MultiTerminal',
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
    icon='common/app_icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MultiTerminal',
)

app = BUNDLE(
    coll,
    name='MultiTerminal.app',
    icon='common/app_icon.icns',
    bundle_identifier='com.epicsafety.mytools.multiterminal',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
    },
)
