# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec for Scout.
# Build with:  pyinstaller installer/scout.spec --noconfirm --clean

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)

# Scout registers commands/providers via imports inside functions, so pull
# in every scout submodule explicitly. keyring loads its Windows backend
# through entry points, which PyInstaller can't see on its own.
hiddenimports = collect_submodules("scout") + [
    "keyring.backends.Windows",
    "win32ctypes.core",
]

icon_path = os.path.join(SPECPATH, "scout.ico")

a = Analysis(
    [os.path.join(SPECPATH, "scout_launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="scout",
    console=True,
    icon=icon_path if os.path.exists(icon_path) else None,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="scout",
    upx=False,
)
