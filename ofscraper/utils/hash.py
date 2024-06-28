import io
import logging
import pathlib

import xxhash

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import get_dupe_media_files, get_dupe_media_hashes

log = logging.getLogger("shared")


fileHashes = {}


def get_hash(file_data, mediatype=None):
    global fileHashes
    hash = None
    if settings.get_hash(mediatype=mediatype) is None:
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
    BUF_SIZE = constants.getattr("BUF_SIZE")
    with open(file_data, "rb") as f:
        buffered_f = io.BufferedReader(f, buffer_size=BUF_SIZE)
        for block in iter(lambda: buffered_f.read(BUF_SIZE), b""):
            hasher.update(block)
    fileHashes[str(file_data)] = hasher.hexdigest()
    return hasher.hexdigest()


def remove_dupes_hash(username, model_id, mediatype=None):
    if not settings.get_hash():
        return
    hashes = get_dupe_media_hashes(username=username, model_id=model_id, mediatype=None)
    for hash in hashes:
        files = get_dupe_media_files(username=username, model_id=model_id, hash=hash)
        filter_files = list(filter(lambda x: pathlib.Path(x).is_file(), files))
        if len(filter_files) < 2:
            continue
        [pathlib.Path(ele).unlink(missing_ok=True) for ele in filter_files[1:]]
    #
