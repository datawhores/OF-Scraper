import shutil
import subprocess
import re
import logging
import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env

log = logging.getLogger("shared")


# --- "Cached" path to the validated FFmpeg binary ---
_ffmpeg_path: str | None = None


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
            quiet=not env.getattr("FFMPEG_OUTPUT_SUBPROCCESS"),
        )
        output = result.stdout + result.stderr

        if re.search(r"ffmpeg version", output, re.IGNORECASE):
            log.info(f"Validation successful: Found valid FFmpeg binary at '{path}'")
            return True
        else:
            log.warning(
                f"Path '{path}' is executable, but output did not confirm it's FFmpeg."
            )
            log.debug(f"Full output from '{path}':\n{output}")
            return False

    except (OSError, subprocess.SubprocessError):
        log.error(
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

    # Step 1: Check the path from settings. (UNCOMMENTED)
    path_from_settings = settings.get_ffmpeg()
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
        log.error(
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
