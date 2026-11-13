"""diskcache disks that read pickled entries as plain data only.

diskcache stores values it can't keep as raw bytes or text with pickle, and
loads them with pickle when they are read, in JSON mode too (CVE-2025-69872).
Someone who can write to the cache folder could plant an entry that runs code
when ofscraper reads it. diskcache has no fix.

ofscraper caches only plain data (API JSON, IDs, flags, timestamps, lists and
tuples), which pickle stores without naming any class. These disks load
pickles with an unpickler that refuses every class or function lookup, so a
planted entry can't run anything. It is treated as missing: diskcache returns
the default for an entry that raises an IOError, and the data is fetched
again.

Cache.get, pop and touch read such an entry as missing. Don't use peek or
peekitem with these disks: diskcache retries an unreadable entry there
without removing it.
"""

import copyreg
import io
import logging
import os.path
import pickle
import pickletools

from diskcache import Disk, JSONDisk
from diskcache.core import MODE_PICKLE

log = logging.getLogger("shared")


class UnsafeCacheEntry(OSError):
    """A cache entry that isn't plain data, read as a cache miss."""


# EXT opcodes name a callable registered with copyreg.add_extension. The
# unpickler resolves one through find_class, which refuses it, unless a load
# has already put it in copyreg's extension cache: then it is returned
# directly. ofscraper registers no extensions, so the cache stays empty and
# the opcode scan below (pure Python, about 15x the cost of the load) only
# runs if something has filled it.
_EXTENSION_OPCODES = {"EXT1", "EXT2", "EXT4"}
# The C unpickler keeps the dict copyreg._extension_cache named when pickle
# was imported; check that one too, in case the module attribute is rebound.
_EXTENSION_CACHE = copyreg._extension_cache


class _PlainDataUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise UnsafeCacheEntry(f"it refers to {module}.{name}")


def _refuse_extensions(data: bytes):
    for opcode, arg, _ in pickletools.genops(data):
        if opcode.name in _EXTENSION_OPCODES:
            raise UnsafeCacheEntry(f"it uses copyreg extension code {arg}")


def _load_plain(data: bytes):
    try:
        if _EXTENSION_CACHE or copyreg._extension_cache:
            _refuse_extensions(data)
        return _PlainDataUnpickler(io.BytesIO(data)).load()
    except UnsafeCacheEntry as error:
        log.warning(f"Ignoring a cache entry that isn't plain data: {error}")
        raise
    except Exception as error:
        # a corrupt or otherwise unreadable entry: also a miss
        raise UnsafeCacheEntry(f"unreadable cache entry: {error}") from error


class _PlainDataMixin:
    def fetch(self, mode, filename, value, read):
        if mode != MODE_PICKLE:
            return super().fetch(mode, filename, value, read)
        if value is None:
            with open(os.path.join(self._directory, filename), "rb") as reader:
                value = reader.read()
        return _load_plain(bytes(value))

    def get(self, key, raw):
        if raw:
            return super().get(key, raw)
        # a pickled key; ofscraper's keys are strings, stored raw
        return _load_plain(bytes(key))


class SafeDisk(_PlainDataMixin, Disk):
    """diskcache's Disk (the sqlite cache mode), reading plain data only."""


class SafeJSONDisk(_PlainDataMixin, JSONDisk):
    """diskcache's JSONDisk (the json cache mode), reading plain data only."""
