from types import SimpleNamespace

import pytest
import xxhash

import ofscraper.commands.metadata.manager as metadata_manager
import ofscraper.utils.hash as hash_utils
import ofscraper.utils.settings as settings


@pytest.fixture
def hashing(monkeypatch):
    monkeypatch.setattr(hash_utils, "fileHashes", {})

    def enable(value):
        monkeypatch.setattr(settings, "get_settings", lambda: SimpleNamespace(hash=value))

    return enable


def _helper(planned, prevData):
    return metadata_manager.MetaDataManager()._metadata_hash_helper(
        SimpleNamespace(trunicated_filepath=planned),
        prevData,
        SimpleNamespace(mediatype="videos"),
    )


def test_hashes_the_existing_planned_file(tmp_path, hashing):
    hashing(True)
    planned = tmp_path / "caption.mp4"
    planned.write_bytes(b"media 1")

    assert _helper(planned, {}) == xxhash.xxh128(b"media 1").hexdigest()


def test_hashes_the_previously_recorded_file(tmp_path, hashing):
    hashing(True)
    (tmp_path / "old.mp4").write_bytes(b"media 2")
    prevData = {"directory": str(tmp_path), "filename": "old.mp4"}

    assert _helper(tmp_path / "missing.mp4", prevData) == xxhash.xxh128(b"media 2").hexdigest()


def test_keeps_the_recorded_hash_when_hashing_is_off(tmp_path, hashing):
    hashing(False)
    planned = tmp_path / "caption.mp4"
    planned.write_bytes(b"media 1")

    assert _helper(planned, {"hash": "recorded"}) == "recorded"
