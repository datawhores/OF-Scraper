# -*- mode: python ; coding: utf-8 -*-
import os

# --- This block makes the spec file self-aware and robust ---
# SPECPATH is a variable provided by PyInstaller containing the path to the spec file's directory.
spec_dir = SPECPATH
# Calculate the project root (one level up from 'specs/')
project_root = os.path.join(spec_dir, '..')
# -----------------------------------------------------------------------

# This block finds the ffmpeg binary to bundle with your app
try:
    from pyffmpeg import FFmpeg
    ffmpeg_binary_path = FFmpeg().get_ffmpeg_bin()
    # The spec format for binaries is a list of tuples: (source_path, destination_in_bundle)
    ffmpeg_binary_tuple = (ffmpeg_binary_path, '.')
    print(f"✅ Found ffmpeg binary to bundle: {ffmpeg_binary_path}")
except Exception as e:
    print(f"⚠️ WARNING: Could not find ffmpeg binary; it will not be bundled. Error: {e}")
    ffmpeg_binary_tuple = None

# This Analysis block contains all the necessary dependency information
a = Analysis(
    # Provide a full, unambiguous path to the main script
    [os.path.join(project_root, 'ofscraper', '__main__.py')],
    # Use the calculated project_root for the path
    pathex=[project_root],
    # Bundle the ffmpeg binary
    binaries=[ffmpeg_binary_tuple] if ffmpeg_binary_tuple else [],
    datas=[],
    # Include the hidden import for diskcache
    hiddenimports=['diskcache'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --- This section defines the one-dir build ---
# The EXE object for a one-dir build includes the binaries and data directly.
# There is no final COLLECT step.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ofscraper_file', # The base name of the output executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)