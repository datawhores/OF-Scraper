import io
import logging
import pathlib

import xxhash

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants

log = logging.getLogger("shared")


fileHashes = {}


def get_hash(file_data, mediatype=None):
    global fileHashes
    hash = None
    if config_data.get_hash(mediatype=mediatype) == None:
        return
    if isinstance(file_data, placeholder.Placeholders):
        file_data = file_data.trunicated_filepath
    if fileHashes.get(str(file_data)):
        hash = fileHashes.get(str(file_data))
    else:
        hasher = xxhash.xxh128()
        BUF_SIZE = constants.getattr("BUF_SIZE")
        with open(file_data, "rb") as f:
            buffered_f = io.BufferedReader(f, buffer_size=BUF_SIZE)
            for block in iter(lambda: buffered_f.read(BUF_SIZE), b""):
                hasher.update(block)
        fileHashes[str(file_data)] = hasher.hexdigest()
        hash = hasher.hexdigest()
    log.debug(f"{file_data} => hash: {hash}")
    return hash


def remove_dupes_hash(username, model_id, mediatype=None):
    if not config_data.get_hash(mediatype=mediatype):
        return
    hashes = operations.get_dupe_media_hashes(
        username=username, model_id=model_id, mediatype=None
    )
    for hash in hashes:
        files = operations.get_dupe_media_files(
            username=username, model_id=model_id, hash=hash
        )
        filter_files = list(filter(lambda x: pathlib.Path(x).is_file(), files))
        if len(filter_files) < 2:
            continue
        [pathlib.Path(ele).unlink(missing_ok=True) for ele in filter_files[1:]]
    #
