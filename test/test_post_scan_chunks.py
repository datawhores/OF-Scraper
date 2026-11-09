"""Chunked timeline, archived and streams scans against a fake paged API.

The cache rows, chunk split, workers and the step that merges their pages are
the real ones; only the database reads/writes and the HTTP client are faked.
"""

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

import ofscraper.data.api.archive as archive
import ofscraper.data.api.streams as streams
import ofscraper.data.api.timeline as timeline

# Posts 1..12, an hour apart, off any whole-second boundary
BASE = 1_700_000_000.25


def ts(post_id):
    return BASE + post_id * 3600


class FakeResponse:
    def __init__(self, data):
        self.status = 200
        self._data = data

    async def json_(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeClient:
    """Paginates oldest-first: afterPublishTime=X returns posts newer than X."""

    def __init__(self, live_ids, page_size=2):
        self.posts = [
            {"id": i, "postedAtPrecise": str(ts(i))} for i in sorted(live_ids)
        ]
        self.page_size = page_size
        self.requests = []

    def requests_async(self, url, **kwargs):
        start = parse_qs(urlsplit(url).query).get("afterPublishTime", [None])[0]
        self.requests.append(start)
        newer = [
            p
            for p in self.posts
            if start is None or float(p["postedAtPrecise"]) > float(start)
        ]
        page = newer[: self.page_size]
        return FakeResponse({"list": page, "hasMore": len(newer) > self.page_size})


AREAS = {
    "timeline": (timeline, "get_timeline_posts_info", "process_tasks"),
    "archived": (archive, "get_archived_post_info", "process_tasks_batch"),
    "streams": (streams, "get_streams_post_info", "process_tasks_batch"),
}


@pytest.fixture(params=sorted(AREAS))
def area(request, monkeypatch):
    module, cache_getter, merge = AREAS[request.param]
    state = SimpleNamespace(cached=[], before=None, flagged=[])

    async def fake_cache(**kwargs):
        return [{"post_id": i, "created_at": ts(i)} for i in state.cached]

    async def fake_mark_deleted(post_ids=None, **kwargs):
        state.flagged.extend(post_ids)

    monkeypatch.setattr(module, cache_getter, fake_cache)
    monkeypatch.setattr(module, "mark_post_as_deleted", fake_mark_deleted)
    monkeypatch.setattr(module, "get_min_posts_batch", lambda total, api: 3)
    monkeypatch.setattr(
        module.settings,
        "get_settings",
        lambda: SimpleNamespace(
            api_cached_disabled=False,
            before=state.before,
            discord_level="OFF",
            log_level="OFF",
            output_level="OFF",
        ),
    )
    monkeypatch.setattr(
        module.progress_utils,
        "api",
        SimpleNamespace(
            add_overall_task=lambda *a, **k: 1,
            update_overall_task=lambda *a, **k: None,
            remove_overall_task=lambda *a, **k: None,
        ),
    )

    def scan(client, after=0):
        async def run():
            split = await module.get_split_array(1, "user", after)
            tasks = module.get_tasks(split, client, 1, "user", after)
            data = await getattr(module, merge)(tasks)
            return split, [p["id"] for p in data]

        return asyncio.run(run())

    state.scan = scan
    return state


def test_multi_chunk_scan_returns_every_post_once(area):
    area.cached = list(range(1, 11))
    client = FakeClient(range(1, 11))

    split, ids = area.scan(client)

    assert len(split) == 4
    assert sorted(ids) == list(range(1, 11))
    assert len(ids) == len(set(ids))
    assert area.flagged == []
    # Each worker stops at the page that holds its last cached post
    assert len(client.requests) <= 9


def test_new_post_older_than_the_cache_is_found(area):
    area.cached = list(range(2, 11))
    client = FakeClient(range(1, 11))

    split, ids = area.scan(client)

    assert len(split) == 3
    assert sorted(ids) == list(range(1, 11))
    assert len(ids) == len(set(ids))


def test_deleted_post_back_at_a_chunk_boundary_is_returned(area):
    # Post 3 was flagged deleted, so it isn't cached; it sits on the page
    # that completes the first chunk [1, 2, 4].
    area.cached = [1, 2, 4, 5, 6, 7, 8, 9, 10]
    client = FakeClient(range(1, 11))

    split, ids = area.scan(client)

    assert [p["post_id"] for p in split[0]] == [1, 2, 4]
    assert sorted(ids) == list(range(1, 11))
    assert len(ids) == len(set(ids))
    assert area.flagged == []


def test_page_crossing_before_keeps_in_range_posts(area):
    # The page [5, 6] straddles --before; 5 is in range, 6 is not
    area.before = ts(5) + 1800
    client = FakeClient(range(1, 11))

    _, ids = area.scan(client)

    assert ids == [1, 2, 3, 4, 5]
    assert len(client.requests) == 3


def test_chunks_past_before_return_nothing_after_it(area):
    area.cached = list(range(1, 11))
    area.before = ts(5) + 1800
    client = FakeClient(range(1, 11))

    _, ids = area.scan(client)

    assert sorted(ids) == [1, 2, 3, 4, 5]


def test_single_chunk_scan_reads_to_the_end(area):
    area.cached = [1, 2]
    client = FakeClient(range(1, 8))

    split, ids = area.scan(client)

    assert len(split) == 1
    assert ids == list(range(1, 8))
    # One page for the worker bridging after=0 to post 1, four for the chunk
    assert len(client.requests) == 5
