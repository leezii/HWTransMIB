# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。可复现,跨平台。

本地(macOS): pyinstaller hwtransmib.spec
CI: 各平台用本 spec(datas 自动适配,无需分隔符)。
"""
import sys

block_cipher = None

a = Analysis(
    ["src/hwtransmib/ui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/hwtransmib/kernel/standard_mibs", "hwtransmib/kernel/standard_mibs"),
        ("src/hwtransmib/ui/resources", "hwtransmib/ui/resources"),
    ],
    hiddenimports=["PySide6"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# macOS 用 .app bundle(windowed),其他平台单文件
if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="hwtransmib",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=False,
        icon="src/hwtransmib/ui/resources/app-icon.icns",
    )
    app = BUNDLE(
        exe,
        name="HWTransMIB.app",
        icon="src/hwtransmib/ui/resources/app-icon.icns",
        bundle_identifier="com.hwtransmib.app",
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="hwtransmib",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=False,
        icon="src/hwtransmib/ui/resources/app-icon.png",
    )
