"""The API cache reads pickled entries as plain data only (CVE-2025-69872):
a planted entry can't run code, and is read as missing."""

import copyreg
import logging
import os
import pickle
from types import SimpleNamespace

import diskcache
import pytest

import ofscraper.utils.cache.cache as ofscraper_cache
import ofscraper.utils.config.data as config_data
from ofscraper.utils.cache.safe_disk import SafeDisk, SafeJSONDisk, UnsafeCacheEntry

ran = []


def planted():
    ran.append(True)
    return "planted value"


class Planted:
    # unpickling this calls planted(); a real one could call os.system
    def __reduce__(self):
        return (planted, ())


@pytest.fixture(autouse=True)
def reset_ran():
    ran.clear()


class _PickleValuesJSONKeys(diskcache.JSONDisk):
    # a json-mode cache row whose key is found by the json mode's lookups
    # but whose value is a pickle
    def store(self, value, read, key=diskcache.core.UNKNOWN):
        return diskcache.Disk.store(self, value, read, key)


def _plant(directory, key, value, disk=diskcache.Disk):
    # what someone with write access to the cache folder could do
    planting_disk = _PickleValuesJSONKeys if disk is SafeJSONDisk else diskcache.Disk
    with diskcache.Cache(str(directory), disk=planting_disk) as writer:
        writer.set(key, value)


# a value small enough to be stored in sqlite, and one big enough
# (over diskcache's 32 KB default) to be stored in a file of its own
PLANTED = [Planted(), [Planted(), "x" * 100_000]]


@pytest.mark.parametrize("disk", [SafeDisk, SafeJSONDisk])
@pytest.mark.parametrize("value", PLANTED, ids=["in sqlite", "in a file"])
def test_planted_entry_is_a_miss_and_runs_nothing(tmp_path, disk, value, caplog):
    _plant(tmp_path, "username_a_creator", value, disk)
    with caplog.at_level(logging.WARNING, logger="shared"):
        with diskcache.Cache(str(tmp_path), disk=disk) as cache:
            assert cache.get("username_a_creator", default="missing") == "missing"
    assert ran == []
    assert "isn't plain data" in caplog.text
    assert "planted" in caplog.text  # names what it refers to


@pytest.mark.parametrize("disk", [SafeDisk, SafeJSONDisk])
def test_planted_key_runs_nothing(tmp_path, disk):
    with diskcache.Cache(str(tmp_path)) as writer:
        writer.set(Planted(), "value")  # a pickled key
    with diskcache.Cache(str(tmp_path), disk=disk) as cache:
        with pytest.raises(UnsafeCacheEntry):
            list(cache.iterkeys())
    assert ran == []


VALUES = [
    {"id": 4242, "username": "a_creator", "posts": [{"id": 1, "text": "hi"}]},
    [1, 2, 3],
    ("tuple", 1, 2.5),
    1730000000.25,
    True,
    None,
    "text",
    {"big": ["y" * 100_000]},  # stored in a file
]


@pytest.mark.parametrize("disk", [SafeDisk, SafeJSONDisk])
@pytest.mark.parametrize("value", VALUES)
def test_plain_data_round_trips(tmp_path, disk, value):
    with diskcache.Cache(str(tmp_path), disk=disk) as cache:
        cache.set("key", value)
    with diskcache.Cache(str(tmp_path), disk=disk) as cache:
        got = cache.get("key")
    if disk is SafeJSONDisk and isinstance(value, tuple):
        assert got == list(value)  # JSON has no tuples, as before
    else:
        assert got == value


def test_entries_written_before_the_change_are_still_read(tmp_path):
    # the sqlite mode's cache written by diskcache's own Disk
    with diskcache.Cache(str(tmp_path)) as old:
        old.set("model_id_a_creator", 4242)
        old.set("purchased_all", [1, 2, 3])
        old.set("check", {"posts": [{"id": 1}], "when": ("t", 1.5)})
    with diskcache.Cache(str(tmp_path), disk=SafeDisk) as cache:
        assert cache.get("model_id_a_creator") == 4242
        assert cache.get("purchased_all") == [1, 2, 3]
        assert cache.get("check") == {"posts": [{"id": 1}], "when": ("t", 1.5)}


@pytest.mark.parametrize("mode, disk", [("sqlite", SafeDisk), ("json", SafeJSONDisk)])
def test_cache_mode_uses_the_safe_disks(mode, disk):
    assert config_data.get_cache_mode(config={"cache-mode": mode}) is disk


def test_ofscraper_cache_reads_a_planted_entry_as_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ofscraper_cache, "cache", None)
    monkeypatch.setattr(
        ofscraper_cache.settings,
        "get_settings",
        lambda: SimpleNamespace(cached_disabled=False),
    )
    monkeypatch.setattr(ofscraper_cache.common_paths, "getcachepath", lambda: str(tmp_path))
    monkeypatch.setattr(ofscraper_cache.data, "get_cache_mode", lambda: SafeDisk)
    try:
        ofscraper_cache.set("username_a_creator", {"name": "A creator"})
        assert ofscraper_cache.get("username_a_creator") == {"name": "A creator"}
        _plant(tmp_path, "username_a_creator", Planted())
        assert ofscraper_cache.get("username_a_creator", default=None) is None
        assert ran == []
    finally:
        ofscraper_cache.close()
        monkeypatch.setattr(ofscraper_cache, "cache", None)


def test_copyreg_extension_codes_are_refused(caplog):
    """An EXT opcode loads a registered callable without find_class."""
    from ofscraper.utils.cache.safe_disk import _load_plain

    copyreg.add_extension("os", "getcwd", 240)
    try:
        # plain pickle hands back os.getcwd for this, and caches it, which
        # is the case the scan is for
        assert pickle.loads(b"\x80\x02\x82\xf0.") is os.getcwd
        with caplog.at_level(logging.WARNING, logger="shared"):
            with pytest.raises(UnsafeCacheEntry):
                _load_plain(b"\x80\x02\x82\xf0.")
        assert "extension code 240" in caplog.text
    finally:
        copyreg.remove_extension("os", "getcwd", 240)
        copyreg.clear_extension_cache()


def test_unregistered_or_uncached_extension_codes_are_refused_without_a_scan(
    monkeypatch,
):
    """With nothing in copyreg's extension cache an EXT opcode can't bypass
    find_class, so the opcode scan is skipped and the load still refuses it."""
    import ofscraper.utils.cache.safe_disk as safe_disk

    def no_scan(data):
        raise AssertionError("scanned with an empty extension cache")

    monkeypatch.setattr(safe_disk, "_refuse_extensions", no_scan)
    assert not copyreg._extension_cache
    # plain data loads without the scan
    assert safe_disk._load_plain(pickle.dumps([{"id": 1}, ("t", 1.5)])) == [
        {"id": 1},
        ("t", 1.5),
    ]
    # an unregistered code fails to resolve
    with pytest.raises(UnsafeCacheEntry):
        safe_disk._load_plain(b"\x80\x02\x82\xf0.")
    # a registered one that isn't cached goes through find_class
    copyreg.add_extension("os", "getcwd", 240)
    try:
        with pytest.raises(UnsafeCacheEntry, match="os.getcwd"):
            safe_disk._load_plain(b"\x80\x02\x82\xf0.")
    finally:
        copyreg.remove_extension("os", "getcwd", 240)


def test_extension_cache_rebound_is_still_scanned(monkeypatch):
    """The C unpickler keeps the original extension-cache dict, so a cached
    extension is refused even if copyreg's attribute is rebound."""
    from ofscraper.utils.cache.safe_disk import _load_plain

    copyreg.add_extension("os", "getcwd", 240)
    try:
        pickle.loads(b"\x80\x02\x82\xf0.")  # cache it in the original dict
        monkeypatch.setattr(copyreg, "_extension_cache", {})
        with pytest.raises(UnsafeCacheEntry, match="extension code 240"):
            _load_plain(b"\x80\x02\x82\xf0.")
    finally:
        monkeypatch.undo()
        copyreg.remove_extension("os", "getcwd", 240)
        copyreg.clear_extension_cache()
