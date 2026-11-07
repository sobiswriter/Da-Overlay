# -*- mode: python ; coding: utf-8 -*-
import platform
import struct
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

bundled_data = [('ui/web', 'ui/web')]
for package in ('google-auth', 'sounddevice', 'cryptography', 'cffi', 'pyasn1', 'pyasn1-modules'):
    bundled_data += copy_metadata(package)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=bundled_data,
    hiddenimports=['webview.platforms.edgechromium', 'webview.platforms.winforms', 'win32crypt', 'win32clipboard'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
# Keep the microphone libraries for this Python architecture, including ASIO.
audio_arch = 'arm64' if platform.machine().lower() in ('arm64', 'aarch64') else '64bit' if struct.calcsize('P') == 8 else '32bit'
a.binaries = [item for item in a.binaries if 'portaudio-binaries' not in item[0] or Path(item[0]).name.startswith('libportaudio' + audio_arch)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Cutex',
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
    icon=['flower.ico'],
)
