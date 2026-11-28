import logging
import os
import pathlib
import platform
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

import ofscraper.utils.config.data as data
import ofscraper.utils.console as console_
import ofscraper.utils.dry_run as dry_run
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.names as names
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
    if dry_run.active():
        return  # a dry run deletes nothing
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


def truncate(path, *, keep_suffix=""):
    return names.truncate(path, keep_suffix=keep_suffix, system=platform.system())


_split_ext = names.split_extension
_longest_fitting = names.longest_fitting
_windows_truncateHelper = names.truncate_windows
_mac_truncateHelper = names.truncate_mac
_mac_name_size = names.mac_name_size
_linux_truncateHelper = names.truncate_linux
get_string_byte_size_unix = names.unix_byte_size
get_string_byte_size_windows = names.windows_byte_size


def validate_directory_parts(parts):
    """Reject a generated directory name that exceeds its platform's component
    limit: on macOS and Linux the name limits truncate() cuts file names to"""
    return names.validate_directory_parts(parts, system=platform.system())


def cleanDB():
    if dry_run.active():
        return  # a dry run deletes nothing
    try:
        pathlib.Path(common_paths.get_profile_path() / "db.lock").unlink(
            missing_ok=True
        )
    except PermissionError:
        pass


def speed_file():
    return pathlib.Path(common_paths.get_profile_path() / "speed.zip")
