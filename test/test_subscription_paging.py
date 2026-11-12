import asyncio
from contextlib import asynccontextmanager
from math import ceil
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

import ofscraper.data.api.subscriptions.subscriptions as subscriptions


WORKERS = [
    (subscriptions.scrape_subscriptions_active, "subscriptionsActiveEP"),
    (subscriptions.scrape_subscriptions_disabled, "subscriptionsExpiredEP"),
]


class SubscriptionServer:
    def __init__(self, raw_total, page_size, hidden=()):
        self.raw_total = raw_total
        self.page_size = page_size
        self.hidden = set(hidden)
        self.offsets = []

    @asynccontextmanager
    async def requests_async(self, *, url):
        query = parse_qs(urlsplit(url).query)
        offset = int(query["offset"][0])
        limit = int(query.get("limit", [self.page_size])[0])
        self.offsets.append(offset)

        async def json_():
            return {
                "list": [
                    {"id": item}
                    for item in range(offset, min(offset + limit, self.raw_total))
                    if item not in self.hidden
                ],
                "hasMore": offset + limit < self.raw_total,
            }

        yield SimpleNamespace(status=200, json_=json_)


def collect(worker, server):
    async def run():
        return [item["id"] async for batch in worker(server) for item in batch]

    return asyncio.run(run())


def override_endpoint(monkeypatch, key, endpoint):
    original = subscriptions.of_env.getattr
    monkeypatch.setattr(
        subscriptions.of_env,
        "getattr",
        lambda name, *args, **kwargs: (
            endpoint if name == key else original(name, *args, **kwargs)
        ),
    )


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
@pytest.mark.parametrize("raw_total", [30, 34])
def test_short_pages_advance_by_requested_limit(worker, endpoint_key, raw_total):
    server = SubscriptionServer(raw_total, 10, hidden=range(2, raw_total, 4))

    assert collect(worker, server) == [
        item for item in range(raw_total) if item not in server.hidden
    ]
    assert server.offsets == list(range(0, raw_total, 10))
    assert len(server.offsets) == ceil(raw_total / 10)


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
def test_custom_endpoint_limit(monkeypatch, worker, endpoint_key):
    override_endpoint(
        monkeypatch, endpoint_key, "https://example.test/subscriptions?limit=7&offset={}"
    )
    server = SubscriptionServer(19, 7, hidden=[2, 5, 8, 12, 16])

    assert collect(worker, server) == [
        item for item in range(19) if item not in server.hidden
    ]
    assert server.offsets == [0, 7, 14]


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
def test_custom_endpoint_without_limit(monkeypatch, worker, endpoint_key):
    override_endpoint(
        monkeypatch, endpoint_key, "https://example.test/subscriptions?offset={}"
    )
    server = SubscriptionServer(8, 3)

    assert collect(worker, server) == list(range(8))
    assert server.offsets == [0, 3, 6]


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
def test_empty_page_with_has_more_reads_later_pages(worker, endpoint_key):
    hidden_count = (subscriptions.MAX_EMPTY_PAGES - 1) * 10
    raw_total = hidden_count + 11
    server = SubscriptionServer(raw_total, 10, hidden=range(hidden_count))

    assert collect(worker, server) == list(range(hidden_count, raw_total))
    assert server.offsets == list(range(0, raw_total, 10))


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
def test_empty_page_without_has_more_stops(worker, endpoint_key):
    server = SubscriptionServer(10, 10, hidden=range(10))

    assert collect(worker, server) == []
    assert server.offsets == [0]


class EmptyPageServer:
    def __init__(self, nonempty_pages=()):
        self.nonempty_pages = set(nonempty_pages)
        self.offsets = []

    @asynccontextmanager
    async def requests_async(self, *, url):
        offset = int(parse_qs(urlsplit(url).query)["offset"][0])
        self.offsets.append(offset)
        assert len(self.offsets) <= 50, "Paging did not stop"

        async def json_():
            return {
                "list": (
                    [{"id": offset}] if len(self.offsets) in self.nonempty_pages else []
                ),
                "hasMore": True,
            }

        yield SimpleNamespace(status=200, json_=json_)


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
def test_consecutive_empty_pages_stop(worker, endpoint_key, caplog):
    server = EmptyPageServer()
    max_empty_pages = subscriptions.MAX_EMPTY_PAGES

    with caplog.at_level("DEBUG", logger="shared"):
        assert collect(worker, server) == []

    assert len(server.offsets) == max_empty_pages
    account = "active" if endpoint_key == "subscriptionsActiveEP" else "expired"
    assert (
        f"{account} subscriptions offset {server.offsets[-1]}: "
        f"paging stopped after {max_empty_pages} consecutive empty pages"
    ) in caplog.text


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
def test_nonempty_page_resets_empty_page_count(worker, endpoint_key):
    max_empty_pages = subscriptions.MAX_EMPTY_PAGES
    server = EmptyPageServer(nonempty_pages=[max_empty_pages])

    assert collect(worker, server) == [(max_empty_pages - 1) * 10]
    assert server.offsets == list(range(0, max_empty_pages * 2 * 10, 10))


class FixedPageServer:
    def __init__(self, count):
        self.count = count
        self.offsets = []

    @asynccontextmanager
    async def requests_async(self, *, url):
        offset = int(parse_qs(urlsplit(url).query)["offset"][0])
        self.offsets.append(offset)
        assert len(self.offsets) <= 2, "Paging did not advance"

        async def json_():
            return {
                "list": [{"id": item} for item in range(offset, offset + self.count)],
                "hasMore": offset == 0,
            }

        yield SimpleNamespace(status=200, json_=json_)


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
@pytest.mark.parametrize("limit", ["0", "-1", "invalid", "1.5"])
def test_invalid_limit_falls_back_to_count(monkeypatch, worker, endpoint_key, limit):
    override_endpoint(
        monkeypatch, endpoint_key,
        f"https://example.test/subscriptions?limit={limit}&offset={{}}",
    )
    server = FixedPageServer(2)

    assert collect(worker, server) == [0, 1, 2, 3]
    assert server.offsets == [0, 2]


@pytest.mark.parametrize("worker,endpoint_key", WORKERS, ids=["active", "expired"])
@pytest.mark.parametrize("limit", ["0", "-1", "invalid", "1.5", None])
def test_empty_page_without_positive_step_stops(
    monkeypatch, worker, endpoint_key, limit
):
    query = "" if limit is None else f"limit={limit}&"
    override_endpoint(
        monkeypatch, endpoint_key,
        f"https://example.test/subscriptions?{query}offset={{}}",
    )
    server = FixedPageServer(0)

    assert collect(worker, server) == []
    assert server.offsets == [0]
