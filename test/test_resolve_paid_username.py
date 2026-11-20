"""resolve_paid_username: the paid-content creator name, public so the GUI can reuse it."""

import asyncio

import pytest

import ofscraper.data.posts.post as post

PLACEHOLDER = "modeldeleted"


@pytest.fixture
def lookups(monkeypatch):
    """Stub the profile and DB lookups; returns (configure, db_calls)."""
    db_calls = []
    state = {}

    async def table_exists(model_id=None, username=None):
        db_calls.append(("exists", model_id, username))
        return state["in_db"]

    async def profile_info(model_id=None, username=None):
        db_calls.append(("info", model_id, username))
        return state["recorded"]

    monkeypatch.setenv("OFSC_DELETED_MODEL_PLACEHOLDER", PLACEHOLDER)
    monkeypatch.setattr(
        post.profile, "scrape_profile", lambda model_id: {"username": state["scraped"]}
    )
    monkeypatch.setattr(post, "check_profile_table_exists", table_exists)
    monkeypatch.setattr(post, "get_profile_info", profile_info)

    def configure(scraped, in_db=None, recorded=None):
        state.update(scraped=scraped, in_db=in_db, recorded=recorded)

    return configure, db_calls


@pytest.mark.parametrize(
    "scraped, in_db, recorded, expected",
    [
        # a live creator: the scraped name, no DB lookup
        ("creator_a", None, None, "creator_a"),
        # deleted, and an earlier run recorded its name
        (PLACEHOLDER, True, "old_name", "old_name"),
        # deleted, in the DB but no name stored
        (PLACEHOLDER, True, None, f"{PLACEHOLDER}_7"),
        # deleted and never seen before
        (PLACEHOLDER, False, None, f"{PLACEHOLDER}_7"),
    ],
)
def test_resolve_paid_username(lookups, scraped, in_db, recorded, expected):
    configure, db_calls = lookups
    configure(scraped, in_db, recorded)

    assert asyncio.run(post.resolve_paid_username(7)) == expected
    if scraped != PLACEHOLDER:
        assert db_calls == []
    elif in_db:
        assert db_calls == [
            ("exists", 7, PLACEHOLDER),
            ("info", 7, PLACEHOLDER),
        ]
    else:
        assert db_calls == [("exists", 7, PLACEHOLDER)]
