"""The archived and streams scans: endpoints, settings keys, logs and DB hooks.

The two areas share one scraper; these pin down what each still does on its
own: which endpoints and env defaults it reads, the lines it logs, what it
flags as deleted and the database functions (patchable on the area module)
that pick where a scan starts.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import arrow
import pytest

import ofscraper.data.api.archive as archive
import ofscraper.data.api.streams as streams
import ofscraper.utils.of_env.of_env as of_env

MODEL_ID = 7
USER = "a creator"
BASE = 1_700_000_000.25

AREAS = {
    "archived": SimpleNamespace(
        module=archive,
        entry="get_archived_posts",
        api="Archived",
        scan_name="archived",
        endpoint="archivedEP",
        next_endpoint="archivedNextEP",
        max_key="MAX_ARCHIVED_INDIVIDUAL_SEARCH",
        post_info="get_archived_post_info",
        media="get_archived_media",
        youngest="get_youngest_archived_date",
        cache_line="[bold]Archived Cache[/bold] {} found",
        ghost_line="Worker finished. Flagging 1 ghost archived posts.",
    ),
    "streams": SimpleNamespace(
        module=streams,
        entry="get_streams_posts",
        api="Streams",
        scan_name="streams",
        endpoint="streamsEP",
        next_endpoint="streamsNextEP",
        max_key="MAX_STREAMS_INDIVIDUAL_SEARCH",
        post_info="get_streams_post_info",
        media="get_streams_media",
        youngest="get_youngest_streams_date",
        cache_line="[bold]Streams Cache[/bold] {} found",
        ghost_line="Worker finished. Flagging 1 ghost streams in database.",
    ),
}


@pytest.fixture(params=sorted(AREAS))
def area(request, monkeypatch):
    spec = AREAS[request.param]
    spec.settings = SimpleNamespace(
        api_cached_disabled=False,
        before=None,
        mediatypes=None,
        post_id=None,
        discord_level="OFF",
        log_level="OFF",
        output_level="OFF",
    )
    monkeypatch.setattr(spec.module.settings, "get_settings", lambda: spec.settings)
    spec.keys = []
    real_getattr = of_env.getattr

    def getattr_(key, *args, **kwargs):
        spec.keys.append(key)
        return real_getattr(key, *args, **kwargs)

    monkeypatch.setattr(of_env, "getattr", getattr_)
    monkeypatch.setattr(
        spec.module.progress_utils,
        "api",
        SimpleNamespace(
            add_overall_task=lambda *a, **k: 1,
            update_overall_task=lambda *a, **k: None,
            remove_overall_task=lambda *a, **k: None,
        ),
    )
    return spec


@pytest.fixture
def logged(caplog):
    caplog.set_level(logging.DEBUG, logger="shared")

    def get(level=None):
        return [
            r.getMessage()
            for r in caplog.records
            if r.name == "shared" and (level is None or r.levelno == level)
        ]

    return get


class Response:
    def __init__(self, status, data=None):
        self.status = status
        self._data = data

    async def json_(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class Client:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.urls = []

    def requests_async(self, url=None, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def ts(n):
    return BASE + n * 3600


def post(n):
    return {"id": n, "postedAtPrecise": str(ts(n))}


def collect(gen):
    async def go():
        return [batch async for batch in gen]

    return asyncio.run(go())


def test_pages_follow_the_area_endpoints(area):
    client = Client(
        Response(200, {"list": [post(1), post(2)], "hasMore": True}),
        Response(200, {"list": [post(3)], "hasMore": False}),
    )
    scrape = area.module.get_tasks([], client, MODEL_ID, USER, 0)[0]

    batches = collect(scrape)

    assert [[p["id"] for p in b] for b in batches] == [[1, 2], [3]]
    assert client.urls == [
        of_env.getattr(area.endpoint).format(MODEL_ID),
        of_env.getattr(area.next_endpoint).format(MODEL_ID, str(ts(2))),
    ]


def test_failed_page_is_logged_with_the_area_name(area, logged, monkeypatch):
    marked = Mock()
    monkeypatch.setattr(area.module.incomplete, "mark_incomplete", marked)
    client = Client(Response(503))
    scrape = area.module.get_tasks([], client, MODEL_ID, USER, 0)[0]

    assert collect(scrape) == []

    url = of_env.getattr(area.endpoint).format(MODEL_ID)
    assert f"{area.api} API Error: 503 for {url}" in logged(logging.DEBUG)
    marked.assert_called_once_with(MODEL_ID, area.api, "HTTP 503")


def test_cached_post_missing_from_the_api_is_flagged(area, logged, monkeypatch):
    flagged = AsyncMock()
    monkeypatch.setattr(area.module, "mark_post_as_deleted", flagged)
    split = [[{"post_id": 2, "created_at": ts(2)}, {"post_id": 9, "created_at": ts(3)}]]
    client = Client(Response(200, {"list": [post(2), post(4)], "hasMore": False}))
    # the bridge worker first, then the chunk
    scrape = area.module.get_tasks(split, client, MODEL_ID, USER, ts(2))[-1]

    collect(scrape)

    flagged.assert_awaited_once_with(post_ids=[9], model_id=MODEL_ID, username=USER)
    assert area.ghost_line in logged(logging.INFO)


def test_cache_rows_are_deduplicated_and_logged(area, logged, monkeypatch):
    rows = [
        {"post_id": 1, "created_at": ts(1)},
        None,
        {"post_id": 1, "created_at": ts(1)},
        {"post_id": 2, "created_at": ts(2)},
    ]
    monkeypatch.setattr(area.module, area.post_info, AsyncMock(return_value=rows))
    monkeypatch.setattr(area.module, "get_min_posts_batch", lambda total, api: 1)

    split = asyncio.run(area.module.get_split_array(MODEL_ID, USER, 0))

    assert [[r["post_id"] for r in chunk] for chunk in split] == [[1], [2]]
    assert area.cache_line.format(2) in logged(logging.DEBUG)


def test_cache_disabled_skips_the_database(area, logged, monkeypatch):
    area.settings.api_cached_disabled = True
    lookup = AsyncMock(return_value=[{"post_id": 1, "created_at": ts(1)}])
    monkeypatch.setattr(area.module, area.post_info, lookup)

    assert asyncio.run(area.module.get_split_array(MODEL_ID, USER, 0)) == []
    lookup.assert_not_awaited()
    assert area.cache_line.format(0) in logged(logging.DEBUG)


def test_scan_range_names_the_area(area, monkeypatch):
    calls = []
    monkeypatch.setattr(
        area.module.scan_range,
        "log_scan_range",
        lambda log, username, name, after: calls.append((username, name, after)),
    )

    area.module.time_log(USER, 5.0)

    assert calls == [(USER, area.scan_name, 5.0)]


@pytest.fixture
def event_loop():
    # the @run entry points use the current loop and leave it open; without
    # one they create a loop that nothing closes
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    asyncio.set_event_loop(None)
    loop.close()


def entry_setup(area, monkeypatch):
    monkeypatch.setattr(area.module, "get_after", AsyncMock(return_value=123.0))
    monkeypatch.setattr(area.module, "time_log", Mock())
    monkeypatch.setattr(area.module.incomplete, "start_scan", lambda m, api, a: a)
    saved = Mock()
    monkeypatch.setattr(area.module.incomplete, "save_scan", saved)
    checked = Mock()
    monkeypatch.setattr(area.module, "update_check", checked)
    return saved, checked


def test_few_post_ids_are_fetched_individually(area, monkeypatch, event_loop):
    saved, checked = entry_setup(area, monkeypatch)
    found = [{"id": 1}]
    monkeypatch.setattr(area.module, "process_posts_as_individual", lambda: found)
    split = AsyncMock()
    monkeypatch.setattr(area.module, "get_split_array", split)

    data = getattr(area.module, area.entry)(MODEL_ID, USER, c=None, post_id=[1, 2])

    assert data == found
    split.assert_not_awaited()
    saved.assert_not_called()
    checked.assert_called_once_with(found, MODEL_ID, 123.0, area.api)
    assert area.max_key in area.keys


def test_many_post_ids_scan_the_area(area, monkeypatch, event_loop):
    saved, checked = entry_setup(area, monkeypatch)
    monkeypatch.setattr(area.module, "get_split_array", AsyncMock(return_value=[]))
    recording = of_env.getattr
    monkeypatch.setattr(
        of_env,
        "getattr",
        lambda key, *a, **k: 1 if key == area.max_key else recording(key, *a, **k),
    )

    async def worker():
        yield [{"id": 5}]

    monkeypatch.setattr(area.module, "get_tasks", lambda *args: [worker()])

    data = getattr(area.module, area.entry)(MODEL_ID, USER, c=None, post_id=[1, 2])

    assert data == [{"id": 5}]
    saved.assert_called_once_with(MODEL_ID, area.api, 123.0, USER)
    checked.assert_called_once_with(data, MODEL_ID, 123.0, area.api)


def media_row(media_id, post_id, posted_at, **extra):
    row = {
        "media_id": media_id,
        "post_id": post_id,
        "posted_at": posted_at,
        "downloaded": 0,
        "unlocked": 1,
        "media_type": "images",
    }
    row.update(extra)
    return row


@pytest.fixture
def after_db(area, monkeypatch):
    db = SimpleNamespace(prechecks=None, media=[], downloaded=[], deleted=[], youngest=None)
    monkeypatch.setattr(
        area.module, "get_after_pre_checks", lambda model_id, api: db.prechecks
    )
    monkeypatch.setattr(
        area.module, area.media, AsyncMock(side_effect=lambda **k: db.media)
    )
    monkeypatch.setattr(
        area.module,
        "get_media_ids_downloaded_model",
        AsyncMock(side_effect=lambda **k: db.downloaded),
    )
    monkeypatch.setattr(
        area.module, "get_deleted_post_ids", AsyncMock(side_effect=lambda **k: db.deleted)
    )
    monkeypatch.setattr(
        area.module, area.youngest, AsyncMock(side_effect=lambda **k: db.youngest)
    )
    return db


def after(area):
    return asyncio.run(area.module.get_after(MODEL_ID, USER))


YEAR_2000 = arrow.get("2000").float_timestamp


def test_after_full_scan_request_is_kept_from_2000(area, after_db):
    after_db.prechecks = 0
    assert after(area) == YEAR_2000
    after_db.prechecks = "2024-01-01T00:00:00"
    assert after(area) == arrow.get("2024-01-01T00:00:00").float_timestamp


def test_after_without_media_starts_in_2000(area, after_db):
    assert after(area) == YEAR_2000


def test_after_everything_downloaded_starts_at_the_newest_post(area, after_db):
    after_db.media = [
        media_row(1, 1, "2024-01-01T00:00:00", downloaded=1),
        media_row(2, 2, "2024-02-01T00:00:00"),
        media_row(3, 3, "2024-03-01T00:00:00", unlocked=0),
        media_row(4, 4, "2024-04-01T00:00:00", media_type="videos"),
    ]
    after_db.downloaded = [2]
    area.settings.mediatypes = ["Images"]
    after_db.youngest = "2024-05-01T00:00:00"

    assert after(area) == arrow.get("2024-05-01T00:00:00").float_timestamp


def test_after_starts_at_the_oldest_missing_media(area, after_db):
    after_db.media = [
        media_row(1, 1, "2024-03-01T00:00:00"),
        media_row(2, 2, "2024-02-01T00:00:00"),
        media_row(3, 3, "2024-01-01T00:00:00"),
    ]
    after_db.deleted = [3]

    assert after(area) == arrow.get("2024-02-01T00:00:00").float_timestamp
