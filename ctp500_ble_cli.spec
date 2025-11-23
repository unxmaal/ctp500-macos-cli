# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for CTP500 BLE CLI
# Creates a standalone single-file executable for macOS

a = Analysis(
    ['ctp500_ble_cli.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'bleak',
        'bleak.backends.corebluetooth',
        'bleak.backends.corebluetooth.client',
        'bleak.backends.corebluetooth.scanner',
        'PIL',
        'PIL._imaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ctp500_ble_cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip symbols to reduce size
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # CLI application
    disable_windowed_traceback=False,
    argv_emulation=False,  # macOS-specific
    target_arch=None,  # Build for current architecture
    codesign_identity=None,  # Set this for code signing if needed
    entitlements_file=None,
)
