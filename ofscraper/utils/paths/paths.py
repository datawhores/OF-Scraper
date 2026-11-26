import logging
import ntpath
import os
import pathlib
import platform
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

import ofscraper.utils.config.data as data
import ofscraper.utils.console as console_
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings

console = console_.get_shared_console()
homeDir = pathlib.Path.home()
log = logging.getLogger("shared")


@contextmanager
def set_directory(path: Path):
    """Sets the cwd within the context

        Args:``
            path (``Path): The path to the cwd

    Yields:
        None
    """

    origin = Path().absolute()
    Path(str(path)).mkdir(parents=True, exist_ok=True)
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


def temp_cleanup():
    from ofscraper.commands.scraper.actions.download import stop

    if stop.requested.is_set():
        return
    if not of_env.getattr("BATCH_TEMPFILE_CLEANUP"):
        return
    if not settings.get_settings().auto_resume:
        log.info("Cleaning up temp files\n\n")
        root = data.get_TempDir()
        if root is None:
            return
        for folder in pathlib.Path(root).glob("**/.*.part.segments"):
            if folder.is_dir():
                shutil.rmtree(folder, ignore_errors=True)
        for file in filter(
            lambda x: x.is_file()
            and re.search(r"\.part$|^temp_", x.name) is not None,
            pathlib.Path(root).glob("**/*"),
        ):
            file.unlink(missing_ok=True)


def truncate(path):
    path = pathlib.Path(os.path.normpath(path))
    if platform.system() == "Windows":
        return _windows_truncateHelper(path)
    elif platform.system() == "Linux":
        return _linux_truncateHelper(path)
    elif platform.system() == "Darwin":
        return _mac_truncateHelper(path)
    else:
        return pathlib.Path(path)


def _split_ext(name):
    """The name without its extension, and the extension (with a "_1"-style
    number before it, which a cut must keep). Taken off the end only."""
    match = re.search(r"_[0-9]+\.[a-z4]*$", name, re.IGNORECASE) or re.search(
        r"\.[a-z4]*$", name, re.IGNORECASE
    )
    ext = match.group(0) if match else ""
    return (name[: -len(ext)] if ext else name), ext


def _longest_fitting(text, size, max_size):
    """The longest start of `text` whose `size` is at most `max_size`."""
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if size(text[:mid]) <= max_size:
            low = mid
        else:
            high = mid - 1
    return text[:low]


def _windows_truncateHelper(path):
    # read by Windows' rules whatever system this runs on (the same thing on
    # Windows), so the tests check it on Linux too
    path = pathlib.PureWindowsPath(ntpath.normpath(path))
    limit = of_env.getattr("WINDOWS_MAX_PATH_BYTES")
    if get_string_byte_size_windows(path) <= limit:
        return pathlib.Path(str(path))
    dir = path.parent
    file, ext = _split_ext(path.name)
    # the whole path counts: the folder, the separator after it (a drive or
    # share root such as C:\ already ends with one), the extension
    sep = "" if str(dir).endswith(ntpath.sep) else ntpath.sep
    max_bytes = (
        limit
        - get_string_byte_size_windows(dir)
        - get_string_byte_size_windows(sep)
        - get_string_byte_size_windows(ext)
    )
    name = _longest_fitting(file, get_string_byte_size_windows, max_bytes)
    if not ext:
        # Windows drops trailing spaces and dots from a name
        name = name.rstrip(" .")
    if not name:
        raise ValueError(f"the folder is too long for any file name to fit: {path}")
    newFile = f"{name}{ext}"
    final_path = pathlib.PureWindowsPath(dir, newFile)
    log.debug(
        f"path: {path} filepath bytesize: {get_string_byte_size_windows(final_path)}"
    )
    return pathlib.Path(str(final_path))


def _mac_truncateHelper(path):
    path = pathlib.Path(os.path.normpath(path))
    if len(str(path)) <= of_env.getattr("MAC_MAX_PATH"):
        return path
    dir = path.parent
    file, ext = _split_ext(path.name)
    maxlength = of_env.getattr("MAC_MAX_PATH") - len(ext)
    newFile = f"{file[:maxlength]}{ext}"
    final = pathlib.Path(dir, newFile)
    log.debug(f"path: {final} path size: {len(str(final))}")
    log.debug(f"path: {final} filename size: {len(str(final.name))}")
    return pathlib.Path(dir, newFile)


def _linux_truncateHelper(path):
    path = pathlib.Path(os.path.normpath(path))
    dir = path.parent
    file, ext = _split_ext(path.name)
    max_bytes = of_env.getattr("LINUX_MAX_FILE_NAME_BYTES") - get_string_byte_size_unix(
        ext
    )
    name = _longest_fitting(file, get_string_byte_size_unix, max_bytes)
    if (file and not name) or max_bytes < 0:
        raise ValueError(f"the name limit leaves no room for any of the name: {path}")
    newFile = f"{name}{ext}"
    log.debug(f"path: {path} filename bytesize: {get_string_byte_size_unix(newFile)}")
    return pathlib.Path(dir, newFile)


def get_string_byte_size_unix(text):
    """
    This function estimates the byte size of a string considering ASCII characters.

    Args:
        text: The string to analyze.

    Returns:
        The estimated byte size of the string.
    """
    total_size = 0
    text = str(text)
    normal_char_size = of_env.getattr("NORMAL_CHAR_SIZE_UNIX")
    special_char_size = of_env.getattr("SPECIAL_CHAR_SIZE_UNIX")
    utf = of_env.getattr("UTF")

    if utf:
        return len(text.encode(utf))
    for char in text:
        try:
            if ord(char) < 128:
                total_size += normal_char_size  # 2 bytes for ASCII characters
            else:
                total_size += special_char_size
        except ValueError:
            total_size += (
                special_char_size  # 4 bytes for non-ASCII characters (assumption)
            )
    return total_size


def get_string_byte_size_windows(text):
    """
    This function estimates the byte size of a string considering ASCII characters.

    Args:
        text: The string to analyze.

    Returns:
        The estimated byte size of the string.
    """
    total_size = 0
    text = str(text)
    normal_char_size = of_env.getattr("NORMAL_CHAR_SIZE_WINDOWS")
    special_char_size = of_env.getattr("SPECIAL_CHAR_SIZE_WINDOWS")
    utf = of_env.getattr("UTF")
    if utf:
        return len(text.encode(utf))
    for char in text:
        try:
            if ord(char) < 128:
                total_size += normal_char_size  # 2 bytes for ASCII characters
            else:
                total_size += special_char_size
        except ValueError:
            total_size += (
                special_char_size  # 4 bytes for non-ASCII characters (assumption)
            )
    return total_size


def cleanDB():
    try:
        pathlib.Path(common_paths.get_profile_path() / "db.lock").unlink(
            missing_ok=True
        )
    except PermissionError:
        pass


def speed_file():
    return pathlib.Path(common_paths.get_profile_path() / "speed.zip")
