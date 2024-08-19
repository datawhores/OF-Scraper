import logging
import os
import pathlib
import platform
import shutil
from collections.abc import Iterable

import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.dates as dates
import ofscraper.utils.paths.common as common_paths
from ofscraper.actions.utils.log import get_medialog

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass


def moveHelper(temp, path_to_file, ele, log_=None):
    if not path_to_file.exists():
        shutil.move(temp, path_to_file)
    elif (
        pathlib.Path(temp).absolute().stat().st_size
        >= pathlib.Path(path_to_file).absolute().stat().st_size
    ):
        shutil.move(temp, path_to_file)
    else:
        pathlib.Path(temp).unlink(missing_ok=True)
        log_ = log_ or logging.getLogger("shared")
        log_.debug(f"{get_medialog(ele)} smaller then previous file")
    # set variables based on parent process


def addGlobalDir(path):
    paths = [path] if not isinstance(path, Iterable) else path
    paths = list(
        map(
            lambda x: (
                path.resolve(x).parent
                if not pathlib.Path(x).is_dir()
                else path.resolve(x)
            ),
            paths,
        )
    )
    common_globals.dirSet.update(paths)


def addLocalDir(path):
    paths = [path] if not isinstance(path, list) else path
    paths = list(
        map(
            lambda x: (
                path.resolve(x).parent
                if not pathlib.Path(x).is_dir()
                else path.resolve(x)
            ),
            paths,
        )
    )
    common_globals.dirSet.update(paths)


def set_time(path, timestamp):
    if platform.system() == "Windows":
        setctime(path, timestamp)
    pathlib.os.utime(path, (timestamp, timestamp))


def setDirectoriesDate(log=None):
    log = log or common_globals.log
    log.info("Setting Date for modified directories")
    output = set()
    rootDir = pathlib.Path(common_paths.get_save_location())
    log.debug(f"Original DirSet {list(common_globals.dirSet)}")
    log.debug(f"rooDir {rootDir}")

    for ele in common_globals.dirSet:
        output.add(ele)
        while not os.path.samefile(ele, rootDir) and not os.path.samefile(
            ele.parent, rootDir
        ):
            common_globals.log.debug(f"Setting Dates ele:{ele} rootDir:{rootDir}")
            output.add(ele.parent)
            ele = ele.parent
    log.debug(f"Directories list {output}")
    for ele in output:
        set_time(ele, dates.get_current_time())
