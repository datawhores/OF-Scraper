import logging
import os
import pathlib
import platform
import errno
import shutil
import tempfile
import time
from collections.abc import Iterable

import xxhash

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.config.data as config_data
import ofscraper.utils.dates as dates
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.paths.paths as path_utils
from ofscraper.commands.scraper.actions.utils.log import get_medialog

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass

MAX_CANDIDATES = 1000
STALE_STAGING_SECONDS = 24 * 60 * 60


def moveHelper(temp, path_to_file, ele, log_=None):
    """
    Move a finished download into place and return the path it ended up at.

    A filename template (e.g. one built on {text}) can give different media
    the same path (#48). A free name is reserved by creating it exclusively
    (O_EXCL), which only one download can do, across threads and processes,
    and then replaced with the download. An existing nonempty file with
    identical content is this download already, so it's kept. Anything else at that
    name, including another download's reservation, is left alone and the
    download goes to name_<media_id>, then name_<media_id>_2 and so on. The
    filesystem decides whether a name is taken, so its own case rules apply.
    Callers must record the returned path. filename_collision "overwrite"
    keeps the old behaviour: the larger file wins.
    """
    log_ = log_ or logging.getLogger("shared")
    path_to_file = pathlib.Path(path_to_file)
    if str(config_data.get_filename_collision()).lower() == "overwrite":
        return _move_overwrite(temp, path_to_file, ele, log_)
    for candidate in _candidates(path_to_file, ele.id):
        if _reserve(candidate):
            _replace_reserved(temp, candidate)
            break
        if _same_content(temp, candidate):
            pathlib.Path(temp).unlink(missing_ok=True)
            break
    else:
        raise RuntimeError(f"{get_medialog(ele)} no free path found for {path_to_file}")
    if candidate != path_to_file:
        log_.debug(
            f"{get_medialog(ele)} {path_to_file.name} holds another file; saved as {candidate.name}"
        )
    return candidate


def _reserve(path):
    """Create path if nothing is there; False if something already is."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0))
    except FileExistsError:
        return False
    os.close(fd)
    return True


def _replace_reserved(temp, path):
    try:
        _replace(temp, path)
    except OSError as E:
        # Copy privately on the destination drive, then publish atomically.
        # Other downloads must never hash a partially copied destination.
        if E.errno == errno.EXDEV or getattr(E, "winerror", None) == 17:
            staged = None
            _sweep_staging(pathlib.Path(path).parent)
            try:
                fd, staged = tempfile.mkstemp(
                    prefix=".ofs-move-", dir=pathlib.Path(path).parent
                )
                os.close(fd)
                # Copy times only once published: an old .part's mtime on the
                # staging file would let another download's sweep remove it.
                shutil.copyfile(temp, staged)
                _replace(staged, path)
            except BaseException:
                pathlib.Path(path).unlink(missing_ok=True)
                raise
            finally:
                if staged is not None:
                    pathlib.Path(staged).unlink(missing_ok=True)
            shutil.copystat(temp, path)
            pathlib.Path(temp).unlink(missing_ok=True)
        else:
            pathlib.Path(path).unlink(missing_ok=True)
            raise


def _sweep_staging(directory):
    # A hard kill mid-copy leaves a staging file behind. A live copy is
    # seconds or minutes old, so anything a day old is abandoned.
    cutoff = time.time() - STALE_STAGING_SECONDS
    for leftover in directory.glob(".ofs-move-*"):
        try:
            if leftover.stat().st_mtime < cutoff:
                leftover.unlink()
        except OSError:
            pass


def _replace(source, destination):
    # Windows can briefly deny replacement while a competing exclusive-open
    # or stat checks the reservation. Keep owning it while retrying.
    for attempt in range(6):
        try:
            os.replace(source, destination)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 5:
                raise
            time.sleep(0.02 * (attempt + 1))


def _move_overwrite(temp, path_to_file, ele, log_):
    if not path_to_file.exists() or (
        pathlib.Path(temp).absolute().stat().st_size
        >= path_to_file.absolute().stat().st_size
    ):
        shutil.move(temp, path_to_file)
    else:
        pathlib.Path(temp).unlink(missing_ok=True)
        log_.debug(f"{get_medialog(ele)} smaller then previous file")
    return path_to_file


def with_media_id(path, media_id, n=1):
    path = pathlib.Path(path)
    tail = f"_{media_id}" if n == 1 else f"_{media_id}_{n}"
    return path.with_name(f"{path.stem}{tail}{path.suffix}")


def _candidates(path, media_id):
    yield path
    for n in range(1, MAX_CANDIDATES):
        # a trailing _<digits> survives truncation, but check the result anyway
        yield pathlib.Path(path_utils.truncate(with_media_id(path, media_id, n)))


def _same_content(a, b):
    a, b = pathlib.Path(a), pathlib.Path(b)
    try:
        # Empty files may be reservations, so never deduplicate against them.
        if (
            not b.is_file()
            or not b.stat().st_size
            or a.stat().st_size != b.stat().st_size
        ):
            return False
        return _file_hash(a) == _file_hash(b)
    except FileNotFoundError:
        # A competing failed move can remove its reservation during this check.
        return False


def _file_hash(path):
    # not hash.get_hash: that caches by path, and these files are replaced
    hasher = xxhash.xxh128()
    size = of_env.getattr("BUF_SIZE")
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(size), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _resolve(path):
    path = pathlib.Path(path)
    try:
        return path.resolve()
    except OSError:
        # some network/virtual drives (e.g. WinError 1005 on mapped Windows
        # volumes) can't be resolved; the directory set is only used to
        # date folders afterwards, so an absolute path is enough
        return path.absolute()


def _resolve_dir(path):
    path = _resolve(path)
    return path if path.is_dir() else path.parent


def addGlobalDir(path):
    paths = (
        [path]
        if isinstance(path, (str, os.PathLike)) or not isinstance(path, Iterable)
        else path
    )
    common_globals.dirSet.update(map(_resolve_dir, paths))


def addLocalDir(path):
    paths = [path] if not isinstance(path, list) else path
    common_globals.dirSet.update(map(_resolve_dir, paths))


def set_time(path, timestamp):
    if platform.system() == "Windows":
        setctime(path, timestamp)
    os.utime(path, (timestamp, timestamp))


def setDirectoriesDate(log=None):
    log = log or common_globals.log
    log.info("Setting Date for modified directories")
    output = set()
    # resolved the same way as dirSet so is_relative_to compares like with like
    # (resolve() can turn a mapped drive letter into a UNC path)
    rootDir = _resolve(common_paths.get_save_location())
    log.debug(f"Original DirSet {list(common_globals.dirSet)}")
    log.debug(f"rootDir {rootDir}")

    for ele in common_globals.dirSet:
        output.add(ele)
        try:
            while not os.path.samefile(ele, rootDir) and not os.path.samefile(
                ele.parent, rootDir
            ):
                if ele.parent in output:
                    # We already added all subsequent paths in this tree
                    break
                if not pathlib.PurePath(ele.parent).is_relative_to(rootDir):
                    # Don't descend if the parent path is outside rootDir such as
                    # when a symlink was used somewhere in the path
                    break
                common_globals.log.debug(f"Setting Dates ele:{ele} rootDir:{rootDir}")
                output.add(ele.parent)
                ele = ele.parent
        except OSError as E:
            # samefile stats both paths, which fails on the same drives
            log.debug(f"could not walk up from {ele}: {E}")
    log.debug(f"Directories list {output}")
    for ele in output:
        try:
            set_time(ele, dates.get_current_time())
        except OSError as E:
            log.debug(f"could not set date on {ele}: {E}")
