"""Fansly messages and purchases one page at a time.

Timeline and walls were already page generators; messages and purchases
were only whole lists. These generators let a caller act on each page as it
arrives. The whole-list functions are built on the same paging, so both
give the same posts. No request is sent anywhere: a fake session answers
each API path and records the order of the calls.
"""

import asyncio
import contextlib
import copy
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

import ofscraper.utils.settings as settings
from ofscraper.sites.fansly import api, constants, scrape

CREATOR_ID = 100000000000000002
OTHER_ID = 100000000000000099
GROUP_ID = "100000000000000143"
BASE_TIME = 1_790_000_000


def envelope(response):
    return {"success": True, "response": response}


class FakeResponse:
    def __init__(self, data):
        self._data = data

    async def json_(self):
        return copy.deepcopy(self._data)


class FakeSession:
    """Answers API paths from a routing function and records each call,
    and anything the test marks with ``note``, in order."""

    def __init__(self, route):
        self.route = route
        self.log = []

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        parsed = urlparse(url)
        path = parsed.path[len(urlparse(constants.API_BASE).path):]
        query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
        self.log.append((path, query))
        yield FakeResponse(self.route(path, query))

    def note(self, what):
        self.log.append(what)

    def paths(self):
        return [x[0] if isinstance(x, tuple) else x for x in self.log]


@pytest.fixture
def fansly(monkeypatch):
    stub = SimpleNamespace(site="fansly", after=None, post_id=None)
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)
    return stub


def image(account_media_id, account_id=CREATOR_ID, url_tag="orders"):
    """An accountMedia with one image whose link says which call gave it."""
    return {
        "id": str(account_media_id),
        "accountId": str(account_id),
        "access": True,
        "createdAt": BASE_TIME,
        "media": {
            "id": str(account_media_id + 5_000_000),
            "mimetype": "image/jpeg",
            "createdAt": BASE_TIME,
            "locations": [
                {"locationId": "1", "location": f"https://cdn.example/{account_media_id}.jpg?from={url_tag}"}
            ],
        },
    }


# ------------------------------------------------------------------ messages


def message(message_id):
    return {
        "id": str(message_id),
        "senderId": str(CREATOR_ID),
        "groupId": GROUP_ID,
        "createdAt": BASE_TIME - message_id % 1000,
        "content": "",
        "attachments": [],
    }


MESSAGE_PAGES = {
    None: [message(i) for i in range(900, 875, -1)],
    "876": [message(i) for i in range(875, 865, -1)],
    "866": [],
}


def messages_route(path, query):
    if path == "messaging/groups":
        return envelope({"data": [{"partnerAccountId": str(CREATOR_ID), "groupId": GROUP_ID}]})
    if path == "message":
        assert query["groupId"] == GROUP_ID
        page = MESSAGE_PAGES[query.get("before")]
        return envelope({"messages": page, "accountMedia": [], "accountMediaBundles": []})
    raise AssertionError(f"unexpected Fansly call {path}")


def test_messages_come_one_page_at_a_time(fansly):
    c = FakeSession(messages_route)

    async def go():
        pages = []
        async with contextlib.aclosing(scrape.message_pages(CREATOR_ID, "a creator", c=c)) as gen:
            async for page in gen:
                c.note(f"page of {len(page)}")
                pages.append([m["id"] for m in page])
        return pages

    pages = asyncio.run(go())
    assert pages == [list(range(900, 875, -1)), list(range(875, 865, -1))]
    # each page is given before the next one is asked for
    assert c.paths() == [
        "messaging/groups", "message", "page of 25", "message", "page of 10", "message",
    ]


def test_the_message_list_is_the_pages_joined(fansly):
    c = FakeSession(messages_route)
    found = asyncio.run(scrape.get_messages(CREATOR_ID, "a creator", c=c))
    assert [m["id"] for m in found] == list(range(900, 865, -1))
    assert c.paths() == ["messaging/groups", "message", "message", "message"]


def test_message_pages_keep_only_the_asked_ids(fansly):
    c = FakeSession(messages_route)

    async def go():
        gen = scrape.message_pages(CREATOR_ID, "a creator", c=c, post_id=["899", 870])
        return [[m["id"] for m in page] async for page in gen]

    assert asyncio.run(go()) == [[899], [870]]


def test_no_conversation_gives_no_pages(fansly):
    c = FakeSession(messages_route)

    async def go():
        return [page async for page in scrape.message_pages(999, "nobody", c=c)]

    assert asyncio.run(go()) == []
    assert c.paths() == ["messaging/groups"]


def test_timeline_pages_with_post_ids_give_one_page(fansly):
    def route(path, query):
        assert path == "post"
        posts = [
            {"id": "11", "createdAt": BASE_TIME, "attachments": []},
            {"id": "12", "createdAt": BASE_TIME, "attachments": []},
        ]
        return envelope({"posts": posts, "accountMedia": [], "accountMediaBundles": []})

    c = FakeSession(route)

    async def go():
        gen = scrape.timeline_pages(CREATOR_ID, "a creator", c=c, post_id=["12"])
        return [[p["id"] for p in page] async for page in gen]

    assert asyncio.run(go()) == [[12]]


# ------------------------------------------------------------------ purchases

CHUNK = api.ACCOUNT_MEDIA_BATCH
# more than two chunks, with another creator's purchases between them
OURS = [10_000 + i for i in range(2 * CHUNK + 20)]
THEIRS = [90_000 + i for i in range(30)]


def orders_response():
    ids = OURS[:CHUNK] + THEIRS + OURS[CHUNK:]
    return {
        "accountMediaOrders": [
            {"accountMediaId": str(i), "createdAt": BASE_TIME} for i in ids
        ],
        "accountMedia": [image(i) for i in OURS] + [image(i, OTHER_ID) for i in THEIRS],
    }


def purchases_route(drop=()):
    fetches = []

    def route(path, query):
        if path == "account/media/orders/":
            return envelope(orders_response())
        if path == "account/media":
            ids = query["ids"].split(",")
            fetches.append(ids)
            tag = f"fetch{len(fetches)}"
            return envelope([image(int(i), url_tag=tag) for i in ids if int(i) not in drop])
        raise AssertionError(f"unexpected Fansly call {path}")

    return route, fetches


def links(page):
    return [m["files"]["full"]["url"].split("?from=")[1] for p in page for m in p["media"]]


def test_purchases_come_in_chunks_with_links_fetched_per_chunk(fansly):
    route, fetches = purchases_route()
    c = FakeSession(route)

    async def go():
        pages = []
        async with contextlib.aclosing(scrape.paid_pages(CREATOR_ID, "a creator", c=c)) as gen:
            async for page in gen:
                c.note(f"chunk of {len(page)}")
                pages.append(page)
        return pages

    pages = asyncio.run(go())
    # the orders are asked for once; each later chunk's media only after
    # the chunk before it was taken
    assert c.paths() == [
        "account/media/orders/", "chunk of 150",
        "account/media", "chunk of 150",
        "account/media", "chunk of 20",
    ]
    assert [[p["id"] for p in page] for page in pages] == [
        OURS[:CHUNK], OURS[CHUNK:2 * CHUNK], OURS[2 * CHUNK:]
    ]
    assert fetches == [[str(i) for i in OURS[CHUNK:2 * CHUNK]], [str(i) for i in OURS[2 * CHUNK:]]]
    # the first chunk keeps the orders' links; the later ones carry the new ones
    assert set(links(pages[0])) == {"orders"}
    assert set(links(pages[1])) == {"fetch1"}
    assert set(links(pages[2])) == {"fetch2"}
    # the raw media the stream downloader reads comes from the same fetch
    raw = pages[2][0]["media"][0]["fansly"]["media"]
    assert raw["locations"][0]["location"].endswith("from=fetch2")
    assert {p["responseType"] for page in pages for p in page} == {"purchased"}


def test_a_purchase_the_new_answer_leaves_out_keeps_its_first_link(fansly):
    missing = OURS[CHUNK + 3]
    route, _ = purchases_route(drop={missing})
    c = FakeSession(route)

    async def go():
        return [page async for page in scrape.paid_pages(CREATOR_ID, "a creator", c=c)]

    second = asyncio.run(go())[1]
    assert [p["id"] for p in second] == OURS[CHUNK:2 * CHUNK]
    kept = next(p for p in second if p["id"] == missing)
    assert links([kept]) == ["orders"]


def test_the_purchase_list_is_still_one_call(fansly):
    route, fetches = purchases_route()
    c = FakeSession(route)
    found = asyncio.run(scrape.get_paid_posts(CREATOR_ID, "a creator", c=c))
    assert [p["id"] for p in found] == OURS
    assert c.paths() == ["account/media/orders/"]
    assert fetches == []
