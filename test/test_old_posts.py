import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.data.api.common.old as old


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(old, "trace_log_raw", lambda *a, **k: None)


def run(rows, cache_disabled=False, monkeypatch=None):
    monkeypatch.setattr(
        old.settings,
        "get_settings",
        lambda: SimpleNamespace(api_cached_disabled=cache_disabled),
    )

    async def db_function(model_id, username):
        return rows

    return asyncio.run(old.get_old_posts(1, "user", db_function, "Timeline"))


def test_dedupes_by_post_id_and_drops_none(monkeypatch):
    rows = [{"post_id": 1}, None, {"post_id": 1}, {"post_id": 2}]
    assert run(rows, monkeypatch=monkeypatch) == [{"post_id": 1}, {"post_id": 2}]


def test_rows_without_post_id_are_kept(monkeypatch):
    rows = [{"post_id": 1}, {"x": 1}, {"x": 2}, {"post_id": 1}]
    assert run(rows, monkeypatch=monkeypatch) == [{"post_id": 1}, {"x": 1}, {"x": 2}]


def test_cache_disabled_skips_db(monkeypatch):
    assert run([{"post_id": 1}], cache_disabled=True, monkeypatch=monkeypatch) == []
