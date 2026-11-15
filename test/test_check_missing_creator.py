"""A creator OnlyFans can't find is skipped; the check table goes on.

The session passes a 404 through instead of raising, so get_id read
``r.json()["id"]`` from OnlyFans' error body and raised KeyError: 'id'.
That stopped the whole check run at the first deleted, renamed or banned
account ("Perform Action(s) failed: KeyError: 'id'"). get_id now warns
and returns None, and each check command skips that creator.
"""

import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check
import ofscraper.data.api.profile as profile

# --- get_id ---------------------------------------------------------------


class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _Session:
    def __init__(self, response):
        self.response = response
        self.urls = []

    @contextlib.contextmanager
    def requests(self, url):
        self.urls.append(url)
        yield self.response


@pytest.fixture
def cache(monkeypatch):
    saved = {}
    monkeypatch.setattr(profile.cache, "get", lambda key, default=None: saved.get(key, default))
    monkeypatch.setattr(profile.cache, "set", lambda key, value, *a, **k: saved.__setitem__(key, value))
    return saved


@pytest.mark.parametrize(
    "response",
    [
        _Response(404, {"error": {"code": 0, "message": "User not found"}}),
        _Response(404, ValueError("not json")),
        _Response(200, {"error": {"message": "something else"}}),
    ],
    ids=["404 error body", "404 not json", "200 without id"],
)
def test_missing_account_warns_and_returns_none(cache, caplog, response):
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert profile.get_id_helper(_Session(response), "gone_creator") is None
    assert "Skipping gone_creator: OnlyFans has no account by that name" in caplog.text
    assert f"HTTP {response.status}" in caplog.text
    # not cached, so a later run asks again
    assert cache == {}


def test_found_account_is_returned_and_cached(cache):
    session = _Session(_Response(200, {"id": 4242, "username": "here"}))
    assert profile.get_id_helper(session, "here") == 4242
    assert cache == {"model_id_here": 4242}
    # the second lookup comes from the cache
    assert profile.get_id_helper(session, "here") == 4242
    assert len(session.urls) == 1


def test_deleted_placeholder_returns_none(cache, caplog):
    name = profile.of_env.getattr("DELETED_MODEL_PLACEHOLDER")
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert profile.get_id_helper(_Session(None), name) is None
    assert "Skipping a deleted account" in caplog.text


def test_deleted_placeholder_names_the_creator_asked_for(cache, caplog):
    """The purchase and stories checks look the profile up first, which turns
    a deleted account into the placeholder; the warning names what was asked."""
    name = profile.of_env.getattr("DELETED_MODEL_PLACEHOLDER")
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert profile.get_id_helper(_Session(None), name, asked_for="gone_creator") is None
    assert "Skipping gone_creator: OnlyFans lists it as a deleted account" in caplog.text


# --- the check commands -----------------------------------------------------

# "gone" sits between two creators that exist, as in the report
NAMES = ["creator_a", "gone", "creator_b"]
IDS = {"creator_a": "111", "creator_b": "222"}


def _run(monkeypatch, retriver):
    fetched = []

    def fetch(*args, **kwargs):
        model = next(str(a) for a in args if str(a) in IDS.values())

        async def inner():
            fetched.append(model)
            return []

        return inner()

    async def nothing(*args, **kwargs):
        return None

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    current = SimpleNamespace(
        force=False,
        file=None,
        url=list(NAMES),
        check_usernames=list(NAMES),
        file_usernames=None,
        check_area=["Timeline"],
        timeline_strict=False,
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(
        check.manager,
        "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)),
    )
    monkeypatch.setattr(check.auth_requests, "make_headers", lambda: None)
    asked = []

    def get_id(name, asked_for=None):
        asked.append(asked_for)
        return IDS.get(name)

    monkeypatch.setattr(check.profile, "get_id", get_id)
    monkeypatch.setattr(check.profile, "scrape_profile", lambda name: {"username": name})
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    for name in ("table_init_create", "make_post_table_changes", "make_messages_table_changes"):
        monkeypatch.setattr(check.operations, name, nothing)
    monkeypatch.setattr(check.timeline, "get_timeline_posts", fetch)
    monkeypatch.setattr(check.messages_, "get_messages", fetch)
    monkeypatch.setattr(check.paid_, "get_paid_posts", fetch)
    monkeypatch.setattr(check.highlights, "get_stories_post", fetch)
    monkeypatch.setattr(check.highlights, "get_highlight_post", fetch)

    async def collect():
        return [str(row[1]) async for row in getattr(check, retriver)()]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yielded = loop.run_until_complete(collect())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    return yielded, fetched, asked


@pytest.mark.parametrize(
    "retriver",
    [
        "post_check_retriver",
        "message_check_retriver",
        "purchase_check_retriver",
        "stories_check_retriver",
    ],
)
def test_check_skips_the_missing_creator_and_goes_on(monkeypatch, retriver):
    yielded, fetched, asked = _run(monkeypatch, retriver)
    # both real creators, in order; nothing for the missing one
    assert yielded == ["111", "222"]
    assert "None" not in fetched and set(fetched) == {"111", "222"}
    if retriver in ("purchase_check_retriver", "stories_check_retriver"):
        # these look the profile up first, so get_id is told the name asked for
        assert asked == NAMES
