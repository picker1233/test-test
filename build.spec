# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

# Add data files
data_files = [
    ('resources', 'resources'),
    ('src/resources', 'src/resources'),
]

# Add Qt plugins
qt_plugins = [
    ('PyQt6/Qt6/plugins/platforms', 'platforms'),
    ('PyQt6/Qt6/plugins/styles', 'styles'),
]

# Hidden imports
hidden_imports = [
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'qasync',
    'aiohttp',
    'aiodns',
    'multidict',
    'yarl',
    'aiosignal',
    'frozenlist',
    'attrs',
    'msal',
    'keyring.backends.Windows',
    'keyring.backends.macOS',
    'keyring.backends.SecretService',
    'keyring.backends.kwallet',
    'pydantic',
    'pathlib',
    'platform',
    'subprocess',
    'zipfile',
    'json',
    'hashlib',
    'asyncio',
    'logging',
    'getpass',
    'urllib.parse',
    'tempfile',
    'shutil',
]

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=data_files + qt_plugins,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
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
    name='MinecraftLauncher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No visible console on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
