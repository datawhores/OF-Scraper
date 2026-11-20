"""Check mode with a Fansly profile.

The check commands only knew OnlyFans: with a Fansly profile they looked
creators up on OnlyFans and fetched OnlyFans' timeline, messages and
purchases. Now they find the creator on Fansly and use the Fansly fetchers,
skip the areas Fansly doesn't have, and refuse the stories check.
"""

import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check

NAMES = ["creator_a", "gone", "creator_b"]
IDS = {"creator_a": 111, "creator_b": 222}


def _not_onlyfans(*args, **kwargs):
    raise AssertionError("an OnlyFans call in a Fansly check")


@pytest.fixture
def fansly_check(monkeypatch):
    fetched = []
    models_asked = []

    def fetch(area):
        async def inner(model_id, username, c=None, post_id=None):
            assert c is not None  # the check's session is passed on
            fetched.append((area, str(model_id), post_id))
            return [{"id": 5, "responseType": "post"}] if post_id else []

        return inner

    async def get_models(usernames=None, c=None):
        models_asked.append((tuple(usernames), c))
        return [
            {"username": n, "id": IDS[n]} for n in usernames if n in IDS
        ]

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
        check_area=["Timeline", "Pinned", "Archived", "Streams"],
        timeline_strict=False,
        command="post_check",
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(check.sites, "is_fansly", lambda: True)
    monkeypatch.setattr(
        check.manager,
        "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)),
    )
    for module, name in [
        (check.auth_requests, "make_headers"),
        (check.profile, "get_id"),
        (check.profile, "scrape_profile"),
        (check.timeline, "get_timeline_posts"),
        (check.messages_, "get_messages"),
        (check.paid_, "get_paid_posts"),
        (check.pinned, "get_pinned_posts"),
        (check.archived, "get_archived_posts"),
        (check.streams, "get_streams_posts"),
    ]:
        monkeypatch.setattr(module, name, _not_onlyfans)
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    for name in ("table_init_create", "make_post_table_changes", "make_messages_table_changes"):
        monkeypatch.setattr(check.operations, name, nothing)
    monkeypatch.setattr(check.fansly_scrape, "get_models", get_models)
    monkeypatch.setattr(check.fansly_scrape, "get_timeline_posts", fetch("timeline"))
    monkeypatch.setattr(check.fansly_scrape, "get_messages", fetch("messages"))
    monkeypatch.setattr(check.fansly_scrape, "get_paid_posts", fetch("paid"))
    return SimpleNamespace(settings=current, fetched=fetched, models_asked=models_asked)


def _collect(retriver):
    async def go():
        return [str(row[1]) async for row in getattr(check, retriver)()]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(go())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


@pytest.mark.parametrize(
    "retriver,areas",
    [
        ("post_check_retriver", {"timeline"}),
        ("message_check_retriver", {"messages", "paid"}),
        ("purchase_check_retriver", {"paid"}),
    ],
)
def test_check_commands_use_fansly(fansly_check, caplog, retriver, areas):
    with caplog.at_level(logging.INFO, logger="shared"):
        yielded = _collect(retriver)
    # both creators, in order; the one Fansly doesn't know is skipped
    assert yielded == ["111", "222"]
    assert "Skipping gone: Fansly has no account by that name" in caplog.text
    assert {area for area, _, _ in fansly_check.fetched} == areas
    assert {model for _, model, _ in fansly_check.fetched} == {"111", "222"}
    # looked up on Fansly with the check's own session
    assert all(c is not None for _, c in fansly_check.models_asked)


def test_post_check_skips_areas_fansly_does_not_have(fansly_check, caplog):
    with caplog.at_level(logging.INFO, logger="shared"):
        _collect("post_check_retriver")
    assert "Fansly has no Pinned, Archived, Streams area; skipped" in caplog.text


def test_stories_check_is_refused_for_fansly(fansly_check, monkeypatch, caplog):
    fansly_check.settings.command = "story_check"
    monkeypatch.setattr(check, "check_auth", _not_onlyfans)
    with caplog.at_level(logging.ERROR, logger="shared"):
        with pytest.raises(SystemExit) as e:
            check.checker()
    assert e.value.code == 1  # refused, so not a success
    assert "The stories check is OnlyFans only" in caplog.text
    # from the menu it goes back to the menu instead of exiting
    assert check.checker(menu=True) is None


@pytest.mark.parametrize(
    "link,expected",
    [
        ("https://fansly.com/creator_a", ("creator_a", 111)),
        ("https://fansly.com/creator_a/posts", ("creator_a", 111)),
        ("fansly.com/creator_b?tab=media", ("creator_b", 222)),
        ("https://fansly.com/post/123456", (None, None)),
        ("https://fansly.com/live/creator_a", (None, None)),
        ("https://fansly.com/messages/123456", (None, None)),
    ],
)
def test_profile_links_name_the_creator(fansly_check, caplog, link, expected):
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert asyncio.run(check._fansly_creator(link, object())) == expected
    if expected == (None, None):
        assert "Skipping a Fansly " in caplog.text and " link: check mode" in caplog.text
        assert fansly_check.models_asked == []  # not looked up as a name


@pytest.mark.parametrize(
    "area,fetcher", [("timeline", "timeline"), ("messages", "messages")]
)
def test_a_failed_fansly_post_is_fetched_again_from_fansly(fansly_check, area, fetcher):
    async def go():
        return await check._fansly_refresh_post(area, "5", 111, "creator_a")

    data = asyncio.run(go())
    assert fansly_check.fetched == [(fetcher, "111", ["5"])]
    assert [p["id"] for p in data] == [5]


def test_failed_purchased_posts_fetch_the_purchases_once(fansly_check, monkeypatch):
    async def purchases(model_id, username, c=None):
        fansly_check.fetched.append(("paid", str(model_id), None))
        return [{"id": 5}, {"id": 6}, {"id": 7}]

    # built as purchase_check builds them, from Fansly's purchase shape
    failed = [
        SimpleNamespace(
            post=check.posts_.Post(
                {"id": i, "responseType": "purchased", "media": []},
                111, "creator_a", purchased=True,
            )
        )
        for i in (5, 6)
    ]
    assert failed[0].post.responsetype.lower() == "purchased"
    monkeypatch.setattr(check.fansly_scrape, "get_paid_posts", purchases)
    monkeypatch.setattr(check.posts_, "Post", lambda p, *a, **k: p)
    processed = []

    async def process(username, model_id, posts):
        processed.extend(posts)

    monkeypatch.setattr(check, "process_post_media", process)
    loop = asyncio.new_event_loop()  # @run uses the thread's loop
    asyncio.set_event_loop(loop)
    try:
        assert check._refresh_failed_posts("creator_a", 111, failed) is True
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert fansly_check.fetched == [("paid", "111", None)]
    assert [p["id"] for p in processed] == [5, 6]


def test_an_area_without_a_single_post_lookup_falls_back(fansly_check):
    assert asyncio.run(check._fansly_refresh_post("stories", "5", 111, "creator_a")) is None
