# -*- mode: python ; coding: utf-8 -*-
import os

# --- THIS BLOCK IS NOW CORRECTED using SPECPATH ---
# SPECPATH is a variable provided by PyInstaller containing the path to the spec file's directory.
spec_dir = SPECPATH
# Calculate the project root (one level up from 'specs/')
project_root = os.path.join(spec_dir, '..')
# ----------------------------------------------------

try:
    from pyffmpeg import FFmpeg
    ffmpeg_binary_path = FFmpeg().get_ffmpeg_bin()
    ffmpeg_binary_tuple = (ffmpeg_binary_path, '.')
    print(f"✅ Found ffmpeg binary to bundle: {ffmpeg_binary_path}")
except Exception as e:
    print(f"⚠️ WARNING: Could not find ffmpeg binary; it will not be bundled. Error: {e}")
    ffmpeg_binary_tuple = None

a = Analysis(
    [os.path.join(project_root, 'ofscraper', '__main__.py')],
    pathex=[project_root],
    binaries=[ffmpeg_binary_tuple] if ffmpeg_binary_tuple else [],
    datas=[],
    hiddenimports=['diskcache'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ofscraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ofscraper_dir' # Changed from 'ofscraper' to 'onescraper_dir'
)