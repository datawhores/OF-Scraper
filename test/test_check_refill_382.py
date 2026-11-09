"""A failed download in a check table refreshes only its own creator (#382)."""

import asyncio
import contextlib
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check

IDS = {"creator_a": "111", "creator_b": "222"}
NAMES = {v: k for k, v in IDS.items()}


def _refill(monkeypatch, command, model_id):
    fetched = []
    processed = []

    def fetch(*args, **kwargs):
        # every API fake records the model id it was asked for
        model = next(str(a) for a in args if str(a) in NAMES)

        async def inner():
            fetched.append(model)
            return []

        return inner()

    async def nothing(*args, **kwargs):
        return None

    async def fake_process(username, model_id, posts):
        processed.append(str(model_id))

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    current = SimpleNamespace(
        command=command,
        force=False,
        file=None,
        url=list(IDS),
        check_usernames=list(IDS),
        file_usernames=None,
        check_area=["Timeline"],
        timeline_strict=False,
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))
    monkeypatch.setattr(check.auth_requests, "make_headers", lambda: None)
    monkeypatch.setattr(check.profile, "get_id", lambda name: IDS[name])
    monkeypatch.setattr(check.profile, "scrape_profile", lambda name: {"username": NAMES.get(name, name)})
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    monkeypatch.setattr(check, "process_post_media", fake_process)
    for name in ("table_init_create", "make_post_table_changes", "make_messages_table_changes"):
        monkeypatch.setattr(check.operations, name, nothing)
    monkeypatch.setattr(check.timeline, "get_timeline_posts", fetch)
    monkeypatch.setattr(check.messages_, "get_messages", fetch)
    monkeypatch.setattr(check.paid_, "get_paid_posts", fetch)
    monkeypatch.setattr(check.highlights, "get_stories_post", fetch)
    monkeypatch.setattr(check.highlights, "get_highlight_post", fetch)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        check.data_refill(model_id)
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    return fetched, processed


@pytest.mark.parametrize("command", ["post_check", "msg_check", "paid_check", "story_check"])
def test_refill_fetches_and_processes_only_the_failing_creator(monkeypatch, command):
    fetched, processed = _refill(monkeypatch, command, 222)
    assert fetched and set(fetched) == {"222"}
    assert processed == ["222"]
