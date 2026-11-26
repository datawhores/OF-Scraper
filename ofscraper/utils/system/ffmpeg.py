import importlib.util
import os
import platform
import shutil
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

    # Step 4: If all methods fail, raise the exception.
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
