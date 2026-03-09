import os
import shutil
import subprocess
import re
import logging
import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env

log = logging.getLogger("shared")


# --- "Cached" path to the validated binaries ---
_ffmpeg_path: str | None = None
_ffprobe_path: str | None = None
_ffprobe_checked: bool = False


def _is_valid_ffmpeg(path: str | None) -> bool:
    """
    Checks if a given path is a real, executable FFmpeg binary. Logs the process.
    """
    if not path or not shutil.which(path):
        log.debug(f"Path '{path}' is not a valid or executable file.")
        return False

    log.debug(f"Running validation check on candidate path: {path}")
    try:
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

        if re.search(r"ffmpeg version", output, re.IGNORECASE):
            log.info(f"Validation successful: Found valid FFmpeg binary at '{path}'")
            return True
        else:
            log.info(
                f"Path '{path}' is executable, but output did not confirm it's FFmpeg."
            )
            log.debug(f"Full output from '{path}':\n{output}")
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
        "or install the 'ffmpeg' extra ('pip install ofscraper[ffmpeg]')"
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
