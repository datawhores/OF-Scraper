import sqlite3
from contextlib import closing
from types import SimpleNamespace

import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.filters.media.filters as filters


def _media(media_id):
    return SimpleNamespace(
        id=media_id, count=0, post=SimpleNamespace(date="2026-01-01")
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "user_data.db"
    # a sqlite3 connection's own context manager commits but doesn't close
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE medias (media_id INTEGER, model_id INTEGER, downloaded INTEGER)")
        conn.executemany(
            "INSERT INTO medias VALUES (?, ?, ?)",
            [(1, 10, 1), (2, 10, 0), (3, 20, 1)],
        )
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, username: path,
    )
    monkeypatch.setattr(filters.separate, "seperate_avatars", lambda m: m)
    return path


def _settings(monkeypatch, **kw):
    ns = SimpleNamespace(**{"force_all": False, "force_model_unique": False, **kw})
    monkeypatch.setattr(filters.settings, "get_settings", lambda: ns)


def test_force_model_unique_reads_this_models_downloads(db, monkeypatch):
    # used to fail with "'coroutine' object is not iterable" (#8)
    _settings(monkeypatch, force_model_unique=True)
    out = filters.previous_download_filter(
        [_media(1), _media(2), _media(3)], username="model", model_id=10
    )
    assert [m.id for m in out] == [2, 3]


def test_default_reads_all_downloads(db, monkeypatch):
    _settings(monkeypatch)
    out = filters.previous_download_filter(
        [_media(1), _media(2), _media(3)], username="model", model_id=10
    )
    assert [m.id for m in out] == [2]


def test_force_all_skips_database(monkeypatch):
    _settings(monkeypatch, force_all=True)
    out = filters.previous_download_filter([_media(1)], username="m", model_id=1)
    assert [m.id for m in out] == [1]
