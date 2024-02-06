import logging
import os
import pathlib
import platform
import re
from contextlib import contextmanager
from pathlib import Path

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths

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


def cleanup():
    if (
        read_args.retriveArgs().no_auto_resume
        or not data.get_part_file_clean()
        or False
    ):
        log.info("Cleaning up temp files\n\n")
        root = pathlib.Path(data.get_TempDir() or common_paths.get_save_location())
        for file in list(
            filter(
                lambda x: re.search("\.part$|^temp_", str(x)) != None, root.glob("**/*")
            )
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


def _windows_truncateHelper(path):
    path = pathlib.Path(os.path.normpath(path))
    if len(str(path)) <= constants.getattr("WINDOWS_MAX_PATH"):
        return path
    path = pathlib.Path(path)
    dir = path.parent
    file = path.name
    match = re.search("_[0-9]+\.[a-z4]*$", path.name, re.IGNORECASE) or re.search(
        "\.[a-z4]*$", path.name, re.IGNORECASE
    )
    if match:
        ext = match.group(0)
    else:
        ext = ""
    # -1 is for / between parentdirs and file
    fileLength = constants.getattr("WINDOWS_MAX_PATH") - len(ext) - len(str(dir)) - 1
    newFile = f"{re.sub(ext,'',file)[:fileLength]}{ext}"
    final = pathlib.Path(dir, newFile)
    log.debug(f"path: {final} path size: {len(str(final))}")
    return pathlib.Path(dir, newFile)


def _mac_truncateHelper(path):
    path = pathlib.Path(os.path.normpath(path))
    if len(str(path)) <= constants.getattr("MAC_MAX_PATH"):
        return path
    dir = path.parent
    match = re.search("_[0-9]+\.[a-z4]*$", path.name, re.IGNORECASE) or re.search(
        "\.[a-z4]*$", path.name, re.IGNORECASE
    )
    ext = match.group(0) if match else ""
    file = re.sub(ext, "", path.name)
    maxlength = constants.getattr("MAC_MAX_PATH") - len(ext)
    newFile = f"{file[:maxlength]}{ext}"
    final = pathlib.Path(dir, newFile)
    log.debug(f"path: {final} path size: {len(str(final))}")
    log.debug(f"path: {final} filename size: {len(str(final.name))}")
    return pathlib.Path(dir, newFile)


def _linux_truncateHelper(path):
    path = pathlib.Path(os.path.normpath(path))
    dir = path.parent
    match = re.search("_[0-9]+\.[a-z4]*$", path.name, re.IGNORECASE) or re.search(
        "\.[a-z4]*$", path.name, re.IGNORECASE
    )
    ext = match.group(0) if match else ""
    file = re.sub(ext, "", path.name)
    maxbytes = constants.getattr("LINUX_MAX_FILE") - len(ext.encode("utf8"))
    small = 0
    large = len(file)
    target = None
    maxLength = constants.getattr("LINUX_MAX_FILE") - len(ext)
    if len(path.name.encode("utf8")) <= maxbytes:
        target = large
    while True and not target:
        if len(file[:large].encode("utf8")) == maxbytes:
            target = large
        elif len(file[:small].encode("utf8")) == maxbytes:
            target = small
        elif large == small:
            target = large
        elif large == small + 1:
            target = small
        elif len(file[:large].encode("utf8")) > maxbytes:
            large = int((small + large) / 2)
        elif len(file[:large].encode("utf8")) < maxbytes:
            small = large
            large = int((large + maxLength) / 2)
    newFile = f"{file[:target]}{ext}"
    log.debug(f"path: {path} filename bytesize: {len(newFile.encode('utf8'))}")
    return pathlib.Path(dir, newFile)


def cleanDB():
    try:
        pathlib.Path(common_paths.get_profile_path() / "db.lock").unlink(
            missing_ok=True
        )
    except PermissionError:
        None


def speed_file():
    return pathlib.Path(common_paths.get_profile_path() / "speed.zip")
