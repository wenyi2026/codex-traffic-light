# -*- mode: python ; coding: utf-8 -*-


EXCLUDES = [
    'PIL',
    'Pillow',
    'numpy',
    'scipy',
    'pandas',
    'matplotlib',
    'tkinter',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
]


a = Analysis(
    ['codex_traffic_light_watcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CodexTrafficLightWatcher',
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
    icon=['codex_traffic_light.ico'],
)
