"""Focused unit tests for manual command URL parsing and fallback helpers."""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.commands.manual as manual


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://onlyfans.com/my/chats/chat/12345/?id=67890",
            ("12345", "67890", "msg"),
        ),
        (
            "https://onlyfans.com/98765/stories/highlights",
            (None, "98765", "highlights"),
        ),
        (
            "https://onlyfans.com/stories/highlights/54321",
            (None, "54321", "highlights"),
        ),
        (
            "https://onlyfans.com/111222/stories",
            (None, "111222", "stories"),
        ),
        (
            "https://onlyfans.com/my/chats/a_creator/?id=999",
            ("a_creator", "999", "msg2"),
        ),
        (
            "https://onlyfans.com/my/chats/a_creator/?firstId=888",
            ("a_creator", "888", "msg2"),
        ),
        (
            "https://onlyfans.com/444555/a_creator",
            ("a_creator", "444555", "post"),
        ),
        (
            "777888",
            (None, "777888", "unknown"),
        ),
        (
            "https://onlyfans.com/settings/account",
            (None, None, None),
        ),
    ],
)
def test_get_info_parses_supported_urls(url, expected):
    assert manual.get_info(url) == expected


def test_url_helper_merges_and_strips_sources(monkeypatch):
    monkeypatch.setattr(
        manual.settings,
        "get_args",
        lambda: {"file": [" https://onlyfans.com/1/a "], "url": ["\t222\n"]},
    )
    assert list(manual.url_helper(["  333  "])) == [
        "https://onlyfans.com/1/a",
        "222",
        "333",
    ]


def _run_unknown(post_id):
    async def go():
        return await manual.unknown_type_helper(post_id)

    return asyncio.run(go())


def test_unknown_type_helper_returns_timeline_post_with_media(monkeypatch):
    post = {"id": 42, "media": [{"id": 1}], "author": {"id": 10}}
    monkeypatch.setattr(manual, "get_individual_timeline_post", lambda pid: post)

    async def unexpected(*a, **k):
        raise AssertionError("paid fallback should not run when timeline post has media")

    monkeypatch.setattr(manual, "_find_paid_post_by_id", unexpected)
    assert _run_unknown("42") is post


def test_unknown_type_helper_falls_back_to_paid_when_timeline_has_no_media(monkeypatch):
    timeline_post = {"id": 42, "media": [], "author": {"id": 10}}
    paid_post = {"id": 42, "media": [{"id": 9}], "author": {"id": 10}}
    monkeypatch.setattr(
        manual, "get_individual_timeline_post", lambda pid: timeline_post
    )
    monkeypatch.setattr(
        manual.profile,
        "scrape_profile",
        lambda mid: {"id": mid, "username": "a_creator"},
    )

    async def fake_paid(post_id, model_id, username):
        assert (post_id, model_id, username) == ("42", 10, "a_creator")
        return paid_post

    monkeypatch.setattr(manual, "_find_paid_post_by_id", fake_paid)
    assert _run_unknown("42") is paid_post


def test_unknown_type_helper_keeps_original_when_paid_fallback_misses(monkeypatch):
    timeline_post = {"id": 42, "media": [], "author": {"id": 10}}
    monkeypatch.setattr(
        manual, "get_individual_timeline_post", lambda pid: timeline_post
    )
    monkeypatch.setattr(
        manual.profile,
        "scrape_profile",
        lambda mid: {"id": mid, "username": "a_creator"},
    )

    async def fake_paid(post_id, model_id, username):
        return None

    monkeypatch.setattr(manual, "_find_paid_post_by_id", fake_paid)
    assert _run_unknown("42") is timeline_post


def test_allow_manual_dupes_sets_force_all(monkeypatch):
    args = SimpleNamespace(force_all=False)
    updated = []
    monkeypatch.setattr(manual.settings, "get_args", lambda: args)
    monkeypatch.setattr(manual.settings, "update_args", updated.append)

    manual.allow_manual_dupes()
    assert args.force_all is True
    assert updated == [args]
