# -*- mode: python ; coding: utf-8 -*-

# This Analysis block is shared between both spec files.
# It finds all dependencies and bundles the ffmpeg binary.
try:
    from pyffmpeg import FFmpeg
    ffmpeg_binary_path = FFmpeg().get_ffmpeg_bin()
    ffmpeg_binary_tuple = (ffmpeg_binary_path, '.')
    print(f"✅ Found ffmpeg binary to bundle: {ffmpeg_binary_path}")
except Exception as e:
    print(f"⚠️ WARNING: Could not find ffmpeg binary; it will not be bundled. Error: {e}")
    ffmpeg_binary_tuple = None

a = Analysis(
    ['ofscraper/__main__.py'],
    pathex=['.'],
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

# This section creates the single-file executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ofscraper', # The base name of the output file
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
# The COLLECT step combines everything into one executable
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ofscraper'
)