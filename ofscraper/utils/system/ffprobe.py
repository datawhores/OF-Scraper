import logging
import pathlib
import re
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.of_env.of_env as env

# Import both binaries!
from ofscraper.utils.system.ffmpeg import get_ffmpeg, get_ffprobe

log = logging.getLogger("shared")


def _get_duration_ffprobe(file_path, ffprobe_path):
    """Primary method: Clean metadata extraction using ffprobe."""
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    result = run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        level=env.getattr("FFPROBE_SUBPROCESS_LEVEL"),
        name="ffprobe",
    )
    return float(result.stdout.strip())


def _get_duration_ffmpeg(file_path, ffmpeg_path):
    """Fallback method: Regex scraping from ffmpeg stderr output."""
    cmd = [ffmpeg_path, "-i", str(file_path)]
    result = run(
        cmd,
        capture_output=True,
        text=True,
        check=False,  # Must be False because ffmpeg exits with code 1 here
        level=env.getattr("FFMPEG_SUBPROCESS_LEVEL"),
        name="ffmpeg",
    )

    # FFmpeg prints metadata to stderr
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        hours, minutes, seconds = match.groups()
        return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    return None


def get_media_duration(file_path):
    """Gets media duration, preferring ffprobe but falling back to ffmpeg if needed."""
    try:
        # Attempt 1: The Proper Way (ffprobe)
        ffprobe_path = get_ffprobe()
        if ffprobe_path:
            try:
                return _get_duration_ffprobe(file_path, ffprobe_path)
            except Exception as e:
                log.debug(
                    f"ffprobe failed for {file_path}, trying ffmpeg fallback. Error: {e}"
                )

        # Attempt 2:  (ffmpeg Fallback)
        ffmpeg_path = get_ffmpeg()
        duration = _get_duration_ffmpeg(file_path, ffmpeg_path)
        if duration is not None:
            return duration

        log.debug(f"Both ffprobe and ffmpeg failed to read duration for {file_path}")
        return None

    except Exception as e:
        log.debug(
            f"Media duration check threw an unexpected error for {file_path}: {e}"
        )
        return None


def verify_media_integrity(file_path, expected_duration_seconds=None):
    """
    Returns True if the media is healthy and within 3 seconds of expected length.
    This protects against API rounding errors and FFmpeg muxing padding.
    """
    actual_duration = get_media_duration(file_path)

    # 1. Container Check: Ensure headers are readable
    if actual_duration is None:
        log.warning(f"File is corrupted or not a valid media file: {file_path}")
        return False

    # 2. Precision Duration Check
    if expected_duration_seconds:
        # Use abs() to handle cases where the file is slightly longer OR shorter
        diff = abs(expected_duration_seconds - actual_duration)

        # 3.0s allows for worst-case API rounding plus FFmpeg audio padding,
        # while still catching actually dropped DASH segments (usually 3-4s each).
        if diff > 3.0:
            log.debug(
                f"Integrity Check Failed: {pathlib.Path(file_path).name}\n"
                f"Expected: {expected_duration_seconds}s | Actual: {actual_duration:.2f}s "
                f"| Diff: {diff:.2f}s (Limit: 3.0s)"
            )
            return False

    log.debug(
        f"Integrity Check Succeed: {pathlib.Path(file_path).name}\n"
        f"Expected: {expected_duration_seconds}s | Actual: {actual_duration:.2f}s "
        f"| Diff: {diff:.2f}s (Limit: 3.0s)"
    )

    return True
