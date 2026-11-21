import io
import itertools
import logging
import os
import pathlib

import xxhash

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations_.wrapper as db_wrapper
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import (
    get_dupe_media_copies,
    point_media_at_kept_files,
)

log = logging.getLogger("shared")


fileHashes = {}


def get_hash(
    file_data,
):
    global fileHashes
    hash = None
    if settings.get_settings().hash is None:
        return
    if isinstance(file_data, placeholder.Placeholders):
        file_data = file_data.trunicated_filepath
    if fileHashes.get(str(file_data)):
        hash = fileHashes.get(str(file_data))
    else:
        hash = _calc_hash(file_data)
    log.debug(f"{file_data} => hash: {hash}")
    return hash


def _calc_hash(file_data):
    hasher = xxhash.xxh128()
    BUF_SIZE = of_env.getattr("BUF_SIZE")
    with open(file_data, "rb") as f:
        buffered_f = io.BufferedReader(f, buffer_size=BUF_SIZE)
        for block in iter(lambda: buffered_f.read(BUF_SIZE), b""):
            hasher.update(block)
    fileHashes[str(file_data)] = hasher.hexdigest()
    return hasher.hexdigest()


def removes_duplicates():
    """Whether remove_hash_match says to delete duplicate files. Only true
    does. The value can come from the environment, as text, and "false" or
    "0" there must not delete anything."""
    value = settings.get_settings().hash
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return value is True


def remove_dupes_hash(username, model_id, mediatypes, stopped=lambda: False):
    """With remove_hash_match on, delete the creator's later copies of a file
    it already has: files of the same media type with the same recorded
    hash. The copy saved first is kept, and the rows that named a deleted
    file are made to name the kept one. Returns the paths deleted.

    `stopped`: asked before each file; nothing more is deleted once it is
    true."""
    if not removes_duplicates():
        return []
    who = dict(username=username, model_id=model_id)
    try:
        rows = get_dupe_media_copies(mediatypes=tuple(mediatypes), **who)
    except db_wrapper.DB_ERRORS as E:
        log.warning(f"Could not look for duplicate files of {username}: {E}")
        return []
    changes = []
    for _, copies in itertools.groupby(
        rows, key=lambda row: (row["media_type"], row["hash"])
    ):
        changes.extend(_remove_copies(list(copies), stopped))
    if changes:
        try:
            point_media_at_kept_files(changes, **who)
        except db_wrapper.DB_ERRORS as E:
            log.warning(
                f"The database of {username} still names the duplicate files"
                f" that were removed: {E}"
            )
    return list(dict.fromkeys(_path(removed) for removed, _ in changes))


def _path(row):
    return pathlib.Path(row["directory"], row["filename"])


def _remove_copies(rows, stopped):
    """Keep the first file that exists and delete the others that are copies
    of it. `rows` are one hash's get_dupe_media_copies rows. Returns a
    (row, kept file's row) pair for each row whose file was deleted.

    A file is only deleted when it is certainly a spare copy:
    - it is another file than the one kept. Several rows can name one file
      (a media in more than one post), and a hard link is the kept file
      under another name;
    - it belongs to another media than the one kept. With allow-dupes a
      media has a file per post on purpose;
    - its content is the kept file's now, whatever was recorded when the two
      were saved. An empty file is never a copy: it is a download that
      went wrong."""
    files = {}
    for row in rows:
        path = _path(row)
        key = os.path.normcase(os.path.abspath(path))
        files.setdefault(key, (path, []))[1].append(row)
    found = [(path, named) for path, named in files.values() if path.is_file()]
    if len(found) < 2:
        return []
    (kept, kept_rows), others = found[0], found[1:]
    kept_media = {str(row["media_id"]) for row in kept_rows}
    kept_hash = None
    changes = []
    for path, named in others:
        if stopped():
            break
        if kept_media & {str(row["media_id"]) for row in named}:
            continue
        try:
            size = os.path.getsize(path)
            if os.path.samefile(kept, path) or not size:
                continue
            if size != os.path.getsize(kept):
                continue
            kept_hash = kept_hash or _calc_hash(kept)
            if _calc_hash(path) != kept_hash or not _delete_copy(kept, path):
                continue
        except OSError as E:
            log.warning(f"Could not remove the duplicate file {path}: {E}")
            continue
        fileHashes.pop(str(path), None)
        changes.extend((row, kept_rows[0]) for row in named)
        log.info(f"Removed {path}: it is a copy of {kept}")
    return changes


def _delete_copy(kept, path):
    """Delete `path` and say whether it went. It is moved aside first, and
    put back if the kept file went with it: the two can be one file reached
    by two routes that the system doesn't report as the same (a share
    mounted twice), and then there is no copy to spare."""
    aside = path.with_name(path.name + ".duplicate")
    if os.path.lexists(aside):
        raise FileExistsError(f"{aside} is in the way")
    os.rename(path, aside)
    try:
        if not os.path.isfile(kept):
            os.rename(aside, path)
            return False
        os.unlink(aside)
    except OSError:
        if os.path.lexists(aside) and not os.path.lexists(path):
            os.rename(aside, path)
        raise
    return True
