"""A scan that loses a page isn't recorded as complete.

The timeline, archived, streams and messages scans start from a point worked
out from the database. The pages a scan did fetch are saved, so when a page
failed (an error, or a non-2xx answer) that point moved past the posts that
were never fetched, and later runs skipped them. Messages are scanned newest
first, so one failed page lost every older message for good.

Now the fetched posts are still returned, the failure is a warning, and the
next run of the area starts where the incomplete scan started.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ofscraper.data.api.common.incomplete as incomplete
from ofscraper.data.api import archive, messages, streams, timeline
from ofscraper.data.api.common.cache import write
from ofscraper.data.posts import post

AFTER = 1000.0
MODEL_ID = 7

AREAS = {
    "timeline": (timeline, "get_timeline_posts", "scrape_timeline_posts"),
    "archive": (archive, "get_archived_posts", "scrape_archived_posts"),
    "streams": (streams, "get_streams_posts", "scrape_stream_posts"),
    "messages": (messages, "get_messages", "scrape_messages"),
}


class FakeCache:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value, **kwargs):
        self.values[key] = value


class FakeResponse:
    def __init__(self, data=None, status=200):
        self.status = status
        self._data = data

    async def json_(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeClient:
    """Answers each request with the next page; a page may be a failure."""

    def __init__(self, pages):
        self.pages = list(pages)

    def requests_async(self, url, **kwargs):
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        if isinstance(page, int):
            return FakeResponse(status=page)
        return FakeResponse(page)


def item(n):
    # dated for every area: posts use postedAtPrecise, messages createdAt
    return {"id": n, "postedAtPrecise": str(n), "createdAt": n}


def page(ids, has_more=True):
    return {"list": [item(n) for n in ids], "hasMore": has_more}


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(incomplete, "cache", fake)
    monkeypatch.setattr(write, "cache", fake)
    incomplete._scans.clear()
    yield fake
    incomplete._scans.clear()


@pytest.fixture
def explicit_after(monkeypatch):
    current = SimpleNamespace(after=None)
    monkeypatch.setattr(
        incomplete, "settings", SimpleNamespace(get_settings=lambda: current)
    )
    monkeypatch.setattr(
        write, "settings", SimpleNamespace(get_settings=lambda: current)
    )
    return current


@pytest.fixture
def warnings(caplog):
    caplog.set_level(logging.INFO, logger="shared")

    def get():
        return [
            r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
        ]

    return get


def setup_area(monkeypatch, area, after=AFTER):
    module, entry, _ = AREAS[area]
    progress = SimpleNamespace(
        add_overall_task=Mock(return_value=1),
        update_overall_task=Mock(),
        remove_overall_task=Mock(),
    )
    monkeypatch.setattr(module.progress_utils, "api", progress)
    monkeypatch.setattr(module, "get_after", AsyncMock(return_value=after))
    monkeypatch.setattr(module, "time_log", Mock())
    split = ([], None) if area == "messages" else []
    monkeypatch.setattr(module, "get_split_array", AsyncMock(return_value=split))
    return getattr(module, entry)


def scan(entry, client, post_id=None):
    async def go():
        return await entry(MODEL_ID, "a creator", c=client, post_id=post_id)

    return asyncio.run(go())


def ids(data):
    return sorted(x["id"] for x in data)


FAILURES = {
    "error": lambda: RuntimeError("connection reset"),
    "status": lambda: 404,
}


@pytest.mark.parametrize("failure", FAILURES)
@pytest.mark.parametrize("area", AREAS)
def test_failed_page_keeps_fetched_posts_and_records_rescan(
    monkeypatch, cache, explicit_after, warnings, area, failure
):
    entry = setup_area(monkeypatch, area)
    client = FakeClient([page([2001, 2002]), FAILURES[failure]()])

    data = scan(entry, client)

    # the page that came back is still used
    assert ids(data) == [2001, 2002]
    # the next run starts where this scan started
    api = AREAS[area][0].API
    assert cache.get(incomplete._cache_key(MODEL_ID, api)) == AFTER
    shown = warnings()
    assert any("scan stopped early" in w for w in shown)
    assert any(f"[a creator] {api} scan is incomplete" in w for w in shown)


@pytest.mark.parametrize("area", AREAS)
def test_complete_scan_records_nothing(monkeypatch, cache, explicit_after, warnings, area):
    entry = setup_area(monkeypatch, area)
    client = FakeClient([page([2001, 2002], has_more=False)])

    assert ids(scan(entry, client)) == [2001, 2002]
    assert cache.values == {}
    assert warnings() == []


@pytest.mark.parametrize("area", AREAS)
def test_next_run_rescans_from_the_incomplete_scan(
    monkeypatch, cache, explicit_after, area
):
    module, _, scraper = AREAS[area]
    entry = setup_area(monkeypatch, area)
    scan(entry, FakeClient([page([2001, 2002]), RuntimeError("boom")]))

    # the saved posts moved the database's start point past the lost page
    entry = setup_area(monkeypatch, area, after=2002.0)
    starts = []
    real_get_tasks = module.get_tasks

    def get_tasks(*args):
        starts.append(args[-1])
        return real_get_tasks(*args)

    monkeypatch.setattr(module, "get_tasks", get_tasks)
    scan(entry, FakeClient([page([2001, 2002, 2003], has_more=False)]))

    assert starts == [AFTER]


@pytest.mark.parametrize("area", AREAS)
def test_rescan_record_cleared_only_after_a_complete_saved_scan(
    monkeypatch, cache, explicit_after, area
):
    module = AREAS[area][0]
    key = incomplete._cache_key(MODEL_ID, module.API)
    entry = setup_area(monkeypatch, area)

    scan(entry, FakeClient([page([2001]), RuntimeError("boom")]))
    write.set_after_checks(MODEL_ID, module.API)
    assert cache.get(key) == AFTER

    # a later failure keeps the earliest start
    entry = setup_area(monkeypatch, area, after=1500.0)
    scan(entry, FakeClient([page([2001]), RuntimeError("boom")]))
    assert cache.get(key) == AFTER

    entry = setup_area(monkeypatch, area, after=2001.0)
    scan(entry, FakeClient([page([2001, 2002], has_more=False)]))
    # not cleared until the area's posts were saved
    assert cache.get(key) == AFTER
    write.set_after_checks(MODEL_ID, module.API)
    assert cache.get(key) is None


def test_post_id_lookup_does_not_clear_the_record(monkeypatch, cache, explicit_after):
    key = incomplete._cache_key(MODEL_ID, messages.API)
    cache.set(key, AFTER)
    entry = setup_area(monkeypatch, "messages", after=2001.0)
    monkeypatch.setattr(messages, "process_messages_as_individual", AsyncMock(return_value=[]))
    real_getattr = messages.of_env.getattr
    monkeypatch.setattr(
        messages.of_env,
        "getattr",
        lambda key, default=None: 10
        if key == "MAX_MESSAGES_INDIVIDUAL_SEARCH"
        else real_getattr(key, default),
    )

    scan(entry, None, post_id=[5])
    write.set_after_checks(MODEL_ID, messages.API)

    assert cache.get(key) == AFTER


def test_explicit_after_is_kept(monkeypatch, cache, explicit_after):
    explicit_after.after = SimpleNamespace(float_timestamp=1800.0)
    cache.set(incomplete._cache_key(MODEL_ID, messages.API), AFTER)
    assert incomplete.start_scan(MODEL_ID, messages.API, 1800.0) == 1800.0


def test_area_saves_fetched_messages_and_keeps_rescan(monkeypatch, cache, explicit_after):
    """Through the real area wrapper: the posts that came back are saved and
    returned for download, and the rescan record survives the save."""
    setup_area(monkeypatch, "messages")
    saved = AsyncMock()
    monkeypatch.setattr(post.operations, "make_messages_table_changes", saved)
    monkeypatch.setattr(post.free, "check_free_size", lambda: True)
    monkeypatch.setattr(post.sites, "is_fansly", lambda: False)
    client = FakeClient([page([2002, 2001]), RuntimeError("boom")])

    async def go():
        return await post.process_messages(MODEL_ID, "a creator", client)

    result = asyncio.run(go())

    assert result is not None
    posts, api = result
    assert api == messages.API
    assert sorted(p.id for p in posts) == [2001, 2002]
    saved.assert_awaited_once()
    assert cache.get(incomplete._cache_key(MODEL_ID, messages.API)) == AFTER
