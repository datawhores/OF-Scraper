import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

import ofscraper.data.api.messages as messages


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
    """Paginates newest-first like the chats API: ?id=X returns messages older than X."""

    def __init__(self, ids, page_size=3):
        # createdAt equals the id, so ordering by id and by time agree
        self.messages = [{"id": i, "createdAt": i} for i in sorted(ids, reverse=True)]
        self.page_size = page_size
        self.cursors = []

    def requests_async(self, url, **kwargs):
        cursor = parse_qs(urlsplit(url).query).get("id", [None])[0]
        self.cursors.append(cursor)
        older = [
            m for m in self.messages if cursor is None or m["id"] < int(cursor)
        ]
        page = older[: self.page_size]
        has_more = len(older) > self.page_size
        return FakeResponse({"list": page, "hasMore": has_more})


def collect(client, **kwargs):
    async def run():
        out = []
        async for batch in messages.scrape_messages(client, 1, "user", **kwargs):
            out.extend(m["id"] for m in batch)
        return out

    return asyncio.run(run())


def test_full_scan_returns_every_message():
    client = FakeClient(range(1, 21))
    assert collect(client, is_last_chunk=True, after=0) == list(range(20, 0, -1))


def test_page_crossing_after_boundary_keeps_in_range_messages():
    # The page [11, 10, 9] straddles after=10; 11 and 10 must not be dropped
    client = FakeClient(range(1, 21))
    assert collect(client, is_last_chunk=True, after=10) == list(range(20, 9, -1))


def test_completed_chunk_keeps_the_page_that_completed_it():
    client = FakeClient(range(1, 21))
    ids = collect(
        client,
        required_posts=[{"post_id": 17, "timestamp": 17}],
        is_last_chunk=False,
        after=0,
    )
    assert ids == [20, 19, 18, 17, 16, 15]


def test_scan_resumes_from_message_id():
    client = FakeClient(range(1, 21))
    ids = collect(client, message_id=12, is_last_chunk=True, after=0)
    assert ids == list(range(11, 0, -1))
    assert client.cursors[0] == "12"


@pytest.fixture
def recorded_tasks(monkeypatch):
    calls = []

    def fake_scrape_messages(c, model_id, username, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(messages, "scrape_messages", fake_scrape_messages)
    return calls


def chunks():
    # Newest-first chunks, as get_split_array produces them
    return [
        [{"post_id": 9, "created_at": 900}, {"post_id": 8, "created_at": 800}],
        [{"post_id": 7, "created_at": 700}, {"post_id": 6, "created_at": 600}],
        [{"post_id": 5, "created_at": 500}],
    ]


def set_before(monkeypatch, before):
    monkeypatch.setattr(
        messages.settings, "get_settings", lambda: SimpleNamespace(before=before)
    )


def test_chunks_continue_from_previous_tail(monkeypatch, recorded_tasks):
    set_before(monkeypatch, None)
    messages.get_tasks(chunks(), "ANCHOR", None, 1, "user", 0)

    assert [t["message_id"] for t in recorded_tasks] == [None, 8, 6]
    assert [t["is_last_chunk"] for t in recorded_tasks] == [False, False, True]
    assert [t["start_timestamp"] for t in recorded_tasks][1:] == [800.0, 600.0]


def test_first_chunk_starts_at_anchor_when_before_is_set(monkeypatch, recorded_tasks):
    set_before(monkeypatch, 5000)
    messages.get_tasks(chunks(), "ANCHOR", None, 1, "user", 0)

    assert [t["message_id"] for t in recorded_tasks] == ["ANCHOR", 8, 6]


def test_empty_cache_scans_from_anchor(monkeypatch, recorded_tasks):
    set_before(monkeypatch, None)
    messages.get_tasks([], "ANCHOR", None, 1, "user", 0)

    assert len(recorded_tasks) == 1
    assert recorded_tasks[0]["message_id"] == "ANCHOR"
    assert recorded_tasks[0]["is_last_chunk"] is True
