import importlib.util
import base64
import os
import platform
import shutil
import signal
import subprocess
import sys
import re
import logging
import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env
from ofscraper.__version__ import __dist_name__

log = logging.getLogger("shared")


# --- "Cached" path to the validated binaries ---
_ffmpeg_path: str | None = None
_ffprobe_path: str | None = None
_ffprobe_checked: bool = False
# ffmpeg binaries that passed the version check but crashed on the MPEG-TS
# sample; used only when no other ffmpeg is found
_crashed: list[str] = []

# A 940-byte MPEG-TS file: 0.05 s of silent MP2 audio. Reading it runs the
# same MPEG-TS reader as a Fansly or HLS join. Some static builds crash there
# on newer Linux systems: they load the system's own text-conversion (gconv)
# modules, which were built for a newer C library than the one inside them.
_TS_SAMPLE = base64.b64decode(
    "R0AREABC8CUAAcEAAP8B/wAB/IAUSBIBBkZGbXBlZwlTZXJ2aWNlMDF3fEPK////////////"
    "////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////"
    "//////////////////////////////////9HQAAQAACwDQABwQAAAAHwACqxBLL/////////"
    "////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////"
    "/////////////////////////////////////////////////////////////////////0dQ"
    "ABAAArASAAHBAADhAPAABOEA8AAsZW9I////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////R0EAMAdQAAB7DH4AAAABwAEogIAFIQAH2GH/9UjE"
    "dVRNpt/+gAAAFVVVVVfffffffffffffffffPvvu7u7rY+WxbHy2LYti2LYti2LY19993d3db"
    "Hy2LY+WxbFsWxbFsWxbGvvvu7u7rY+WxbHy2LYti2LYti2LY19993d3dbHy2LY+WxbFsWxbF"
    "sWxbGvvvu7u7rY+WxbHy2LYti2LYti2LY19993d3dbHy2LY+WxbFsWxbFsWxbGvvvu5HAQAx"
    "OQD/////////////////////////////////////////////////////////////////////"
    "/////+7utj5bFsfLYti2LYti2LYtjX333d3d1sfLYtj5bFsWxbFsWxbFsa+++7u7utj5bFsf"
    "LYti2LYti2LYtjX333d3d1sfLYtj5bFsWxbFsWxbFsa+++7u7utj5bFsfLYti2LYti2LYtjX"
    "333d3d1sfLYtj5bFsWxbFsWxbFsaAA=="
)

_CRASH_SIGNALS = {"SIGSEGV", "SIGBUS", "SIGILL", "SIGFPE", "SIGABRT"}
# Windows codes for a process ended by the user, not a crash
_WINDOWS_STOPS = {
    0xC000013A: "Ctrl+C or the console closed",  # STATUS_CONTROL_C_EXIT
    0x40010004: "ended by a debugger",  # DBG_TERMINATE_PROCESS
    0x40010005: "Ctrl+C",  # DBG_CONTROL_C
    0x40010008: "Ctrl+Break",  # DBG_CONTROL_BREAK
}


def stop_reason(returncode) -> str | None:
    """How ffmpeg ended when it did not exit by itself: stopped by a signal
    (Linux, macOS) or by a Windows exception code. None for a normal exit."""
    if returncode is None:
        return None
    if returncode < -255:
        # no signal is that large: a Windows code read as signed
        returncode &= 0xFFFFFFFF
    if returncode in _WINDOWS_STOPS:
        return f"was stopped (Windows 0x{returncode:08X}, {_WINDOWS_STOPS[returncode]})"
    if returncode < 0:
        try:
            name = signal.Signals(-returncode).name
        except ValueError:
            name = f"signal {-returncode}"
        return f"crashed ({name})" if name in _CRASH_SIGNALS else f"was stopped ({name})"
    # NTSTATUS error codes (0xC0000005, 0xE06D7363...); a negative exit code,
    # exit(-1), shows as 0xFFFFFFFF, so the top of the range isn't a crash
    if 0xC0000000 <= returncode < 0xF0000000:
        return f"crashed (Windows error 0x{returncode:08X})"
    return None


def _ts_crash(path: str) -> str | None:
    """How ``path`` crashed reading the MPEG-TS sample, or None if it did not.
    A normal error exit (a build without the MPEG-TS reader) is not a crash."""
    try:
        result = subprocess.run(
            [path, "-nostdin", "-loglevel", "error", "-f", "mpegts", "-i", "pipe:0",
             "-c", "copy", "-f", "null", "-"],
            input=_TS_SAMPLE,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        log.debug(f"Could not run the MPEG-TS check on '{path}'.", exc_info=True)
        return None
    reason = stop_reason(result.returncode)
    if reason and not reason.startswith("crashed"):
        # killed from outside (out of memory, a shutdown): not a broken build
        log.warning(f"The MPEG-TS check on '{path}' {reason}; not counted as a crash.")
        return None
    return reason


def _same_binary(path: str) -> str:
    """``path`` as the file it names, so one ffmpeg found by two spellings
    (relative and absolute, a symbolic link, another case on Windows) is
    one."""
    return os.path.normcase(os.path.realpath(shutil.which(path) or path))


def ffmpeg_version(path: str | None):
    """What `path -version` says: (is it ffmpeg, the version text or None,
    the major version or None for a build without one, e.g. from git).
    Raises OSError or SubprocessError when it can't be run."""
    result = run(
        [path, "-version"],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        level=env.getattr("FFMPEG_SUBPROCESS_LEVEL"),
        name="ffmpeg",
    )
    output = result.stdout + result.stderr
    if not re.search(r"ffmpeg version", output, re.IGNORECASE):
        log.debug(f"Full output from '{path}':\n{output}")
        return False, None, None
    text = re.search(r"ffmpeg version\s+(\S+)", output, re.IGNORECASE)
    # the major version number (e.g., "ffmpeg version 6.1.1" -> 6)
    major = re.search(r"ffmpeg version\s+([0-9]+)\.", output, re.IGNORECASE)
    return True, text.group(1) if text else None, int(major.group(1)) if major else None


def pyffmpeg_bin():
    """Where pyffmpeg keeps its ffmpeg, without importing pyffmpeg: importing
    it makes ~/.pyffmpeg, and FFmpeg() unpacks its ffmpeg (about 190 MB)
    there. (is pyffmpeg installed, the path the binary is or will be at)."""
    try:
        installed = importlib.util.find_spec("pyffmpeg") is not None
    except (ImportError, ValueError):
        # ValueError: a module put in sys.modules without a spec
        installed = "pyffmpeg" in sys.modules
    # pyffmpeg's misc.Paths rule
    windows = platform.system().lower() == "windows"
    home = os.environ.get("USERPROFILE" if windows else "HOME")
    if not installed or not home:
        return installed, None
    return True, os.path.join(home, ".pyffmpeg", "bin", "ffmpeg.exe" if windows else "ffmpeg")


def find_ffmpeg(configured: str | None):
    """The ffmpeg get_ffmpeg() would use, without keeping it or unpacking
    pyffmpeg's: (path, where it was found, version text), or (None, None,
    None). Each place is tried in get_ffmpeg's order: the setting, pyffmpeg,
    then PATH. A pyffmpeg ffmpeg that isn't unpacked yet is what a run would
    use; it's given with no version, as only unpacking it could tell."""

    def candidates():
        yield "config", configured
        installed, bundled = pyffmpeg_bin()
        if installed and bundled and not os.path.exists(bundled):
            yield "pyffmpeg, not unpacked yet: a run unpacks it", bundled
        elif installed:
            yield "pyffmpeg", bundled
        yield "PATH", shutil.which("ffmpeg")

    for source, path in candidates():
        if source.startswith("pyffmpeg,"):
            return path, source, None
        if _is_valid_ffmpeg(path):
            try:
                return path, source, ffmpeg_version(path)[1]
            except (OSError, subprocess.SubprocessError):
                continue
    return None, None, None


def _is_valid_ffmpeg(path: str | None) -> bool:
    if path and _same_binary(path) in map(_same_binary, _crashed):
        return False  # already checked in this search, e.g. config.json names the one on PATH
    return _check_ffmpeg(path)


def _check_ffmpeg(path: str | None) -> bool:
    """
    Checks if a given path is a real, executable FFmpeg binary and validates
    that its version is >= 6 for DRM compatibility. Logs the process.
    """
    if not path or not shutil.which(path):
        log.debug(f"Path '{path}' is not a valid or executable file.")
        return False

    log.debug(f"Running validation check on candidate path: {path}")
    try:
        is_ffmpeg, _version, major_version = ffmpeg_version(path)

        if is_ffmpeg:
            if major_version is not None:
                if major_version < 6:
                    log.warning(
                        f"⚠️ Invalid FFmpeg version {major_version}.x detected at '{path}'.\n"
                        f"DRM decryption requires FFmpeg version 6 or newer.\n"
                        f"Skipping this binary and looking for an alternative..."
                    )
                    return False
            else:
                log.debug(f"Could not parse strict semantic version from '{path}' (likely a git/custom build). Allowing it to pass.")

            crash = _ts_crash(path)
            if crash:
                log.warning(
                    f"⚠️ The FFmpeg at '{path}' {crash} reading a small test video, "
                    "so it can't join Fansly or HLS downloads. Some static builds do "
                    "this on newer Linux systems. Looking for another FFmpeg; to choose "
                    "one, set \"ffmpeg\" in config.json, for example to your system's "
                    "own ffmpeg (/usr/bin/ffmpeg on most Linux systems)."
                )
                _crashed.append(path)
                return False

            log.info(f"Validation successful: Found valid FFmpeg binary at '{path}'")
            return True
        else:
            log.info(
                f"Path '{path}' is executable, but output did not confirm it's FFmpeg."
            )
            return False

    except (OSError, subprocess.SubprocessError):
        log.debug(
            f"Execution failed for binary at '{path}'. It may be incompatible or corrupt.",
            exc_info=True,
        )
        return False

def get_ffmpeg() -> str:
    """
    Finds and returns the full path to a validated FFmpeg executable, logging its progress.

    The function determines and validates the path in the following order of precedence:
    1. Check if a validated path has already been found and cached.
    2. Check for a path defined in settings.
    3. Attempt to find the binary bundled with the 'pyffmpeg' library.
    4. Fallback to checking if 'ffmpeg' is in the system's PATH.

    Returns:
        str: The absolute path to the FFmpeg executable.

    Raises:
        FileNotFoundError: If a validated FFmpeg binary cannot be found.
    """
    global _ffmpeg_path

    if _ffmpeg_path:
        return _ffmpeg_path

    log.debug("Searching for a valid FFmpeg binary...")
    _crashed.clear()  # from an earlier search

    # Step 1: Check the path from settings.
    path_from_settings = settings.get_settings().ffmpeg
    log.debug(f"Checking settings for ffmpeg path. Found: '{path_from_settings}'")
    if _is_valid_ffmpeg(path_from_settings):
        _ffmpeg_path = path_from_settings
        return _ffmpeg_path

    # Step 2: Try the optional pyffmpeg library.
    log.debug(
        "Settings path invalid or not found. Attempting to use 'pyffmpeg' library."
    )
    try:
        from pyffmpeg import FFmpeg

        pyffmpeg_path = FFmpeg().get_ffmpeg_bin()
        if _is_valid_ffmpeg(pyffmpeg_path):
            _ffmpeg_path = pyffmpeg_path
            return _ffmpeg_path
    except ImportError:
        log.debug("'pyffmpeg' not installed. Skipping.")
    except Exception:
        log.debug(
            "The 'pyffmpeg' library is installed but failed to provide a valid binary.",
            exc_info=True,
        )

    # Step 3: Fallback to system PATH.
    log.debug("No valid binary from settings or pyffmpeg. Checking system PATH.")
    system_path = shutil.which("ffmpeg")
    if _is_valid_ffmpeg(system_path):
        _ffmpeg_path = system_path
        return _ffmpeg_path

    # Step 4: an ffmpeg that crashed on the MPEG-TS check can still do other
    # work (DRM decryption reads MP4), so use it rather than none.
    if _crashed:
        log.warning(
            f"⚠️ No other FFmpeg was found, so using '{_crashed[0]}', which crashed "
            "on the test video. Fansly and HLS downloads will likely fail with it."
        )
        _ffmpeg_path = _crashed[0]
        return _ffmpeg_path

    # Step 5: If all methods fail, raise the exception.
    raise FileNotFoundError(
        "A valid FFmpeg executable could not be found.\n"
        "Please add FFmpeg to your system's PATH, specify its location in your settings, "
        f"or install the 'ffmpeg' extra ('pip install {__dist_name__}[ffmpeg]')"
    )


def get_ffprobe() -> str | None:
    """
    Finds the ffprobe binary by looking in the exact same folder as ffmpeg.
    Returns None if it cannot be found, allowing for graceful fallbacks.
    Results are cached to prevent redundant disk I/O on bulk downloads.
    """
    global _ffprobe_path
    global _ffprobe_checked

    # 1. Check the cache first!
    if _ffprobe_path:
        return _ffprobe_path

    # If we already searched and failed, don't search again
    if _ffprobe_checked:
        return None

    # Mark that we are actively performing the check
    _ffprobe_checked = True

    try:
        ffmpeg_path = get_ffmpeg()
    except FileNotFoundError:
        return None

    # 2. Look right next to the ffmpeg executable
    ffprobe_dir = os.path.dirname(ffmpeg_path)
    ffprobe_name = "ffprobe.exe" if ffmpeg_path.lower().endswith(".exe") else "ffprobe"
    bundled_ffprobe = os.path.join(ffprobe_dir, ffprobe_name)

    if os.path.exists(bundled_ffprobe):
        _ffprobe_path = bundled_ffprobe
        return _ffprobe_path

    # 3. Fallback to global system path just in case
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        _ffprobe_path = system_ffprobe
        return _ffprobe_path

    log.debug(
        "Found ffmpeg, but could not locate ffprobe. Will rely on ffmpeg fallback."
    )
    return None
