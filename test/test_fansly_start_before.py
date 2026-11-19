"""Fansly: with --before the scan starts at that date.

A timeline or message scan always began at the newest item and paged down,
about one API call every 6 seconds, so ``--before`` on a large creator paged
through every newer post first only to drop it. A Fansly id starts with the
time it was made and the API takes any such number as its ``before`` cursor,
so the first page asked for can be the one at the date. No request is sent
anywhere: the fake session of test_fansly_page_generators answers each call.
"""

import asyncio
import time
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.utils.settings as settings
from ofscraper.sites.fansly import api, scrape

from test_fansly_page_generators import (
    CREATOR_ID,
    GROUP_ID,
    FakeSession,
    envelope,
)

DAY = 24 * 3600
# a --before date well in the past
BEFORE = arrow.get(2024, 3, 1)
PER_PAGE = 3


def made_at(seconds, sequence=7):
    """An id as Fansly makes them: the time, then a counter."""
    return (int((seconds - api.ID_EPOCH) * 1000) << api.ID_TIME_SHIFT) + sequence


# a post every 10 days, the newest 15 days after the --before date
POSTS = [made_at(BEFORE.float_timestamp + 15 * DAY - n * 10 * DAY) for n in range(8)]


def created(item_id):
    return int((item_id >> api.ID_TIME_SHIFT) / 1000 + api.ID_EPOCH)


def older_than(cursor):
    """What the API answers: the newest items below the cursor, 0 for all."""
    cursor = int(cursor or 0)
    return [i for i in POSTS if not cursor or i < cursor][:PER_PAGE]


def route(path, query):
    if path == f"timelinenew/{CREATOR_ID}":
        posts = [
            {"id": str(i), "createdAt": created(i), "attachments": []}
            for i in older_than(query["before"])
        ]
        return envelope({"posts": posts, "accountMedia": [], "accountMediaBundles": []})
    if path == "messaging/groups":
        return envelope({"data": [{"partnerAccountId": str(CREATOR_ID), "groupId": GROUP_ID}]})
    if path == "message":
        found = [
            {"id": str(i), "senderId": str(CREATOR_ID), "groupId": GROUP_ID,
             "createdAt": created(i), "content": "", "attachments": []}
            for i in older_than(query.get("before"))
        ]
        return envelope({"messages": found, "accountMedia": [], "accountMediaBundles": []})
    raise AssertionError(f"unexpected Fansly call {path}")


@pytest.fixture
def given(monkeypatch):
    """Settings as the command line leaves them: without --before the
    setting holds a date four days ahead and ``before_original`` is empty."""
    stub = SimpleNamespace(
        site="fansly", after=None, post_id=None,
        before=arrow.now().shift(days=4), before_original=None,
    )
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)

    def give(date):
        stub.before = stub.before_original = date

    stub.give = give
    return stub


def timeline(c):
    async def go():
        gen = scrape.timeline_pages(CREATOR_ID, "a creator", c=c)
        return [[p["id"] for p in page] async for page in gen]

    return asyncio.run(go())


def messages(c):
    async def go():
        gen = scrape.message_pages(CREATOR_ID, "a creator", c=c)
        return [[m["id"] for m in page] async for page in gen]

    return asyncio.run(go())


def cursors(c, path):
    return [query.get("before") for called, query in c.log if called == path]


# ------------------------------------------------------------------ the cursor


def test_the_cursor_is_an_id_of_the_time_plus_the_slack():
    moment = BEFORE.float_timestamp
    cursor = int(api.cursor_before(moment))
    assert created(cursor) == int(moment) + api.BEFORE_SLACK
    # an id made inside the slack is below it, one made after the slack isn't
    assert made_at(moment + api.BEFORE_SLACK - 2) < cursor
    assert made_at(moment + api.BEFORE_SLACK + 2) > cursor


def test_a_time_before_the_first_id_never_asks_for_the_newest_page():
    # "0" is the API's word for the newest page
    assert api.cursor_before(api.ID_EPOCH - 10 * DAY) == "1"
    assert api.cursor_before(0) == "1"


# ------------------------------------------------------------------ timeline


def test_the_timeline_starts_at_the_before_date(given):
    given.give(BEFORE)
    c = FakeSession(route)
    pages = timeline(c)
    # the two posts newer than the date are never asked for
    assert pages == [POSTS[2:5], POSTS[5:8]]
    first, *rest = cursors(c, f"timelinenew/{CREATOR_ID}")
    assert first == api.cursor_before(BEFORE.float_timestamp)
    # the pages after it are asked for with the last post's id, as before
    assert rest == [str(POSTS[4]), str(POSTS[7])]


def test_the_timeline_keeps_a_post_made_at_the_before_date(given):
    # --before is "at or before": the post made in that very second is kept
    given.give(arrow.get(created(POSTS[2])))
    assert timeline(FakeSession(route))[0][0] == POSTS[2]


def test_before_and_after_together_ask_only_for_the_range(given):
    given.give(BEFORE)
    given.after = arrow.get(created(POSTS[3]) - DAY)
    c = FakeSession(route)
    # one page: it starts at --before and reaches below --after
    assert timeline(c) == [POSTS[2:5]]
    assert len(cursors(c, f"timelinenew/{CREATOR_ID}")) == 1


@pytest.mark.parametrize("case", ["not given", "a date ahead", "a moment ago"])
def test_without_a_before_date_in_the_past_the_timeline_starts_at_the_newest(given, case):
    if case == "a date ahead":
        given.give(arrow.now().shift(days=2))
    elif case == "a moment ago":
        # inside the slack: the cursor would be an id of the future
        given.give(arrow.get(time.time() - api.BEFORE_SLACK / 2))
    c = FakeSession(route)
    assert timeline(c)[0] == POSTS[:PER_PAGE]
    assert cursors(c, f"timelinenew/{CREATOR_ID}")[0] == "0"


def test_a_wall_is_still_scanned_from_its_newest_post(given):
    # Labels keeps its own record of the posts it has seen, as on OnlyFans
    given.give(BEFORE)
    c = FakeSession(route)

    async def go():
        gen = scrape.label_pages(c, {"id": ""}, CREATOR_ID)
        return [[p["id"] for p in page] async for page in gen]

    assert asyncio.run(go())[0] == POSTS[:PER_PAGE]
    assert cursors(c, f"timelinenew/{CREATOR_ID}")[0] == "0"


# ------------------------------------------------------------------ messages


def test_messages_start_at_the_before_date(given):
    given.give(BEFORE)
    c = FakeSession(route)
    assert messages(c) == [POSTS[2:5], POSTS[5:8]]
    first, *rest = cursors(c, "message")
    assert first == api.cursor_before(BEFORE.float_timestamp)
    assert rest == [str(POSTS[4]), str(POSTS[7])]


def test_without_a_before_date_messages_start_at_the_newest(given):
    c = FakeSession(route)
    assert messages(c)[0] == POSTS[:PER_PAGE]
    # the first call carries no cursor at all, as before
    assert cursors(c, "message")[0] is None
