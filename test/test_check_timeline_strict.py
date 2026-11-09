"""post_check applies timeline_strict to timeline posts, as a normal scrape does (#329)."""

import asyncio
import contextlib
from types import SimpleNamespace

import ofscraper.commands.check as check


def _post(post_id, media_id, **extra):
    return {"id": post_id, "media": [{"id": media_id, "canView": True}], **extra}


TIMELINE = [_post(1, 101), _post(7, 107, isPinned=True), _post(8, 108, isArchived=True)]
ARCHIVED = [_post(2, 102, isArchived=True)]
PINNED = [_post(3, 103, isPinned=True)]
LABELS = [{"id": 9, "name": "a label", "posts": [_post(4, 104)]}]
STREAMS = [_post(5, 105, streamId=77)]


def _run_post_check(monkeypatch, timeline_strict, timeline=TIMELINE, archived=ARCHIVED, pinned=PINNED, labels=LABELS):
    # the real post_check retriever, with the API calls and the database faked
    async def fake_timeline(model_id, username, c=None):
        return list(timeline)

    async def fake_archived(model_id, username, c=None):
        return list(archived)

    async def fake_pinned(model_id, c=None):
        return list(pinned)

    async def fake_labels(model_id, c=None):
        return list(labels)

    async def fake_streams(model_id, username, c=None):
        return list(STREAMS)

    async def nothing(*args, **kwargs):
        return None

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    current = SimpleNamespace(
        force=False,
        file=None,
        url=["a_creator"],
        check_area=["Timeline", "Archived", "Pinned", "Labels", "Streams"],
        timeline_strict=timeline_strict,
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    monkeypatch.setattr(check.profile, "get_id", lambda name: 12345)
    monkeypatch.setattr(check.operations, "table_init_create", nothing)
    monkeypatch.setattr(check.operations, "make_label_table_changes", nothing)
    monkeypatch.setattr(check.operations, "make_post_table_changes", nothing)
    monkeypatch.setattr(check.timeline, "get_timeline_posts", fake_timeline)
    monkeypatch.setattr(check.archived, "get_archived_posts", fake_archived)
    monkeypatch.setattr(check.pinned, "get_pinned_posts", fake_pinned)
    monkeypatch.setattr(check.labels, "get_labels", fake_labels)
    monkeypatch.setattr(check.streams, "get_streams_posts", fake_streams)

    async def collect():
        return [item async for item in check.post_check_retriver()]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(collect())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert len(results) == 1
    user_name, model_id, posts = results[0]
    assert (user_name, model_id) == ("a_creator", 12345)
    return posts


def _ids(posts):
    return [p.id for p in posts]


def test_timeline_strict_leaves_pinned_and_archived_out_of_timeline_posts(monkeypatch):
    posts = _run_post_check(monkeypatch, timeline_strict=True)
    ids = _ids(posts)
    assert 1 in ids
    assert 7 not in ids
    assert 8 not in ids


def test_timeline_strict_off_lists_every_timeline_post(monkeypatch):
    posts = _run_post_check(monkeypatch, timeline_strict=False)
    ids = _ids(posts)
    assert [i for i in ids if i in (1, 7, 8)] == [1, 7, 8]


def test_timeline_strict_does_not_change_other_areas(monkeypatch):
    strict = _ids(_run_post_check(monkeypatch, timeline_strict=True))
    loose = _ids(_run_post_check(monkeypatch, timeline_strict=False))
    timeline_ids = {1, 7, 8}
    others = [i for i in loose if i not in timeline_ids]
    assert [i for i in strict if i not in timeline_ids] == others
    # pinned, archived and labels posts are listed in that order, and only once
    assert others[:3] == [3, 2, 4]


def test_timeline_strict_with_empty_areas(monkeypatch):
    # empty lists compare equal, so nothing may pick the timeline posts out by value
    posts = _run_post_check(monkeypatch, timeline_strict=True, archived=[], pinned=[], labels=[])
    assert [i for i in _ids(posts) if i != 5] == [1]
    posts = _run_post_check(monkeypatch, timeline_strict=True, timeline=[])
    assert [i for i in _ids(posts) if i != 5] == [3, 2, 4]


def test_timeline_strict_only_filters_the_timeline_area(monkeypatch):
    # labels holding the same posts as the timeline keep their pinned and archived posts
    same = [{"id": 9, "name": "a label", "posts": list(TIMELINE)}]
    posts = _run_post_check(monkeypatch, timeline_strict=True, labels=same)
    assert _ids(posts).count(7) == 1
    assert _ids(posts).count(8) == 1
    assert _ids(posts).count(1) == 2
