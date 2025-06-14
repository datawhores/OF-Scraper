# -*- mode: python ; coding: utf-8 -*-

# --- Add this block to find the ffmpeg binary ---
try:
    from pyffmpeg import FFmpeg
    ffmpeg_binary_path = FFmpeg().get_ffmpeg_bin()
    ffmpeg_binary_tuple = (ffmpeg_binary_path, '.')
    print(f"✅ Found ffmpeg binary to bundle: {ffmpeg_binary_path}")
except Exception as e:
    print(e)
    print(f"⚠️ WARNING: Could not find ffmpeg binary; it will not be bundled. Error: {e}")
    ffmpeg_binary_tuple = None
# ------------------------------------------------


a = Analysis(
    ['ofscraper/__main__.py'],
    pathex=['.'],
    binaries=[ffmpeg_binary_tuple] if ffmpeg_binary_tuple else [],
    datas=[],
    # --- THIS IS THE FIX ---
    # Add any modules that PyInstaller can't find automatically to this list.
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
    a.binaries,
    a.datas,
    [],
    name='ofscraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)