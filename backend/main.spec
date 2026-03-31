# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

qt_extra_trees = []
if sys.platform.startswith("linux"):
    try:
        import PySide6

        pyside6_qt_dir = Path(PySide6.__file__).resolve().parent / "Qt"
        for subdir in ("lib", "plugins", "qml"):
            qt_path = pyside6_qt_dir / subdir
            if qt_path.exists():
                qt_extra_trees.append(Tree(str(qt_path), prefix=f"PySide6/Qt/{subdir}"))
    except ImportError:
        pass

block_cipher = None


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("./web/index.html", "web/."),
        ("./web/favicon.ico", "web/."),
        ("./web/logo.svg", "web/."),
        ("./web/assets", "web/assets"),
        ("./assets", "assets"),
    ],
    hiddenimports=[
        "api",
        "models",
        "utilities",
        "worker",
        "tiktoken_ext.openai_public",
        "tiktoken_ext",
        "pyecharts",
        "kombu.transport.sqlalchemy",
        "webview.platforms.qt",
        "qtpy",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
    ],
    hookspath=["./hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
for qt_tree in qt_extra_trees:
    a.datas += qt_tree

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VectorVein",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="web/assets/favicon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="vector-vein",
)
