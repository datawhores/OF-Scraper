"""Check commands: paid lookups, -f files and msg_check's help (#202)."""

import ast
import asyncio
import contextlib
import gc
import io
import pathlib
import sys
import warnings
from types import SimpleNamespace

import click
import pytest

import ofscraper.commands.check as check
import ofscraper.utils.args.parse.commands.message as message
import ofscraper.utils.args.parse.commands.paid as paid_cmd
import ofscraper.utils.args.parse.commands.story as story_cmd


def test_get_paid_ids_passes_username_then_id(monkeypatch):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    calls = []

    async def fake_get_paid_posts(username, model_id, c=None):
        calls.append((username, model_id))
        return []

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    async def no_media(*args):
        return []

    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    monkeypatch.setattr(check.paid_, "get_paid_posts", fake_get_paid_posts)
    monkeypatch.setattr(check, "process_post_media", no_media)
    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(force=False))
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))

    try:
        check.get_paid_ids(12345, "a_creator")
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert calls == [("a_creator", 12345)]


def test_every_paid_lookup_in_check_passes_username_first():
    tree = ast.parse(pathlib.Path(check.__file__).read_text(encoding="utf-8"))
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get_paid_posts"
    ]
    assert len(calls) == 3
    for call in calls:
        assert [a.id for a in call.args[:2]] == ["user_name", "model_id"], ast.unparse(call)


def _parse(command, args):
    return command.main(args=args, standalone_mode=False, prog_name="OF-Scraper")


def test_paid_check_reads_usernames_from_a_file(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("creator_one\ncreator_two\n", encoding="utf-8")
    params, _ = _parse(paid_cmd.paid_check, ["-f", str(f)])
    assert set(params["file_usernames"]) == {"creator_one", "creator_two"}


def test_story_check_reads_usernames_from_a_file(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("creator_one\n", encoding="utf-8")
    params, _ = _parse(story_cmd.story_check, ["-f", str(f)])
    assert set(params["file_usernames"]) == {"creator_one"}


def _usage_error_warnings(command, args):
    # a usage error after -f was read must not leave the file open (#220)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(click.UsageError):
            _parse(command, args)
        gc.collect()
    return [w for w in caught if issubclass(w.category, ResourceWarning)]


def test_paid_check_usage_error_closes_the_username_file(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("creator_one\n", encoding="utf-8")
    assert _usage_error_warnings(paid_cmd.paid_check, ["-u", "a", "-f", str(f)]) == []


def test_msg_check_usage_error_closes_the_url_file(tmp_path):
    f = tmp_path / "urls.txt"
    f.write_text("https://onlyfans.com/1/a\n", encoding="utf-8")
    args = ["--url", "https://onlyfans.com/2/b", "-f", str(f)]
    assert _usage_error_warnings(message.message_check, args) == []


def test_check_file_from_stdin_is_read_and_left_open(monkeypatch):
    stdin = io.StringIO("creator_one\ncreator_two\n")
    monkeypatch.setattr(sys, "stdin", stdin)
    params, _ = _parse(paid_cmd.paid_check, ["-f", "-"])
    assert set(params["file_usernames"]) == {"creator_one", "creator_two"}
    assert not stdin.closed


def test_check_usernames_combines_u_and_f(monkeypatch):
    current = SimpleNamespace(check_usernames=["from_u"], file_usernames=["from_f"])
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    assert check.check_usernames() == ["from_u", "from_f"]
    current.check_usernames = None
    assert check.check_usernames() == ["from_f"]


def _post(post_id, media_id, **extra):
    return {"id": post_id, "media": [{"id": media_id, "canView": True}], **extra}


def _run_post_check(monkeypatch):
    # the real post_check retriever, with the API calls and the database faked
    calls = []

    async def fake_timeline(model_id, username, c=None):
        calls.append("Timeline")
        return [_post(1, 101)]

    async def fake_archived(model_id, username, c=None):
        calls.append("Archived")
        return [_post(2, 102, isArchived=True)]

    async def fake_pinned(model_id, c=None):
        calls.append("Pinned")
        return [_post(3, 103, isPinned=True)]

    async def fake_labels(model_id, c=None):
        calls.append("Labels")
        return [{"id": 9, "name": "a label", "posts": [_post(4, 104)]}]

    async def fake_streams(model_id, username, c=None):
        calls.append("Streams")
        return [_post(5, 105, streamId=77), _post(6, 106, streamId=78)]

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
        timeline_strict=False,
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
    user_name, model_id, posts, _ = results[0]
    assert (user_name, model_id) == ("a_creator", 12345)
    return calls, posts


def test_post_check_lists_streams_posts_and_media(monkeypatch):
    calls, posts = _run_post_check(monkeypatch)
    assert "Streams" in calls
    streams_posts = [p for p in posts if p.responsetype == "Streams"]
    assert sorted(p.id for p in streams_posts) == [5, 6]
    assert sorted(m.id for p in streams_posts for m in p.all_media) == [105, 106]


def test_post_check_other_areas_are_listed_as_before(monkeypatch):
    calls, posts = _run_post_check(monkeypatch)
    assert sorted(calls) == ["Archived", "Labels", "Pinned", "Streams", "Timeline"]
    by_id = {p.id: p for p in posts if p.responsetype != "Streams"}
    assert sorted(by_id) == [1, 2, 3, 4]
    assert by_id[2].responsetype == "Archived"
    assert by_id[3].responsetype == "Pinned"
    assert sorted(m.id for i in (1, 2, 3, 4) for m in by_id[i].all_media) == [101, 102, 103, 104]


def test_msg_check_help_describes_messages():
    assert message.message_check.name == "msg_check"
    assert "messages" in message.message_check.short_help
    assert "post_check" not in message.message_check.help


def _run_msg_check(monkeypatch, inputs):
    # drives the real retriever; profile lookups and the cache are faked
    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    async def nothing(*args, **kwargs):
        return None

    ids = {"a_creator": "111", "user123": "222"}
    names = {v: k for k, v in ids.items()}
    looked_up = []
    warned = []

    def scrape_profile(model_id):
        looked_up.append(("id", model_id))
        return {"username": names.get(model_id, "creator_" + model_id)}

    def get_id(username):
        looked_up.append(("name", username))
        return ids.get(username, "999")

    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(force=False, file=None, url=inputs))
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))
    monkeypatch.setattr(check.profile, "scrape_profile", scrape_profile)
    monkeypatch.setattr(check.profile, "get_id", get_id)
    monkeypatch.setattr(check, "read_check", lambda *a: [])
    monkeypatch.setattr(check.operations, "table_init_create", nothing)
    monkeypatch.setattr(check.operations, "make_messages_table_changes", nothing)
    monkeypatch.setattr(check.log, "warning", lambda msg, *a, **k: warned.append(msg))

    async def collect():
        return [(name, model_id) async for name, model_id, *_ in check.message_check_retriver()]

    return asyncio.run(collect()), looked_up, warned


def test_msg_check_skips_unmatched_input_and_checks_the_rest(monkeypatch):
    checked, _, warned = _run_msg_check(monkeypatch, ["onlyfans.com/my/chats", "a_creator"])
    assert checked == [("a_creator", "111")]
    assert len(warned) == 1 and "onlyfans.com/my/chats" in warned[0]


def test_msg_check_skips_blank_line(monkeypatch):
    checked, looked_up, _ = _run_msg_check(monkeypatch, ["", "a_creator"])
    assert checked == [("a_creator", "111")]
    assert looked_up == [("name", "a_creator")]


def test_msg_check_reads_username_with_digits_as_username(monkeypatch):
    checked, looked_up, _ = _run_msg_check(monkeypatch, ["user123"])
    assert looked_up == [("name", "user123")]
    assert checked == [("user123", "222")]


def test_msg_check_reads_chat_link_and_bare_id_as_model_id(monkeypatch):
    checked, looked_up, _ = _run_msg_check(
        monkeypatch, ["https://onlyfans.com/my/chats/chat/111/", "222"]
    )
    assert looked_up == [("id", "111"), ("id", "222")]
    assert checked == [("a_creator", "111"), ("user123", "222")]


def test_msg_check_reads_message_link_without_chat_part_as_model_id(monkeypatch):
    # the app's own message link format, my/chats/<id>/?id=<message id>
    checked, looked_up, warned = _run_msg_check(
        monkeypatch,
        ["https://onlyfans.com/my/chats/111/?id=999", "https://onlyfans.com/my/chats/a_creator/?id=999"],
    )
    assert looked_up == [("id", "111")]
    assert checked == [("a_creator", "111")]
    assert len(warned) == 1 and "my/chats/a_creator" in warned[0]


def test_msg_check_unmatched_input_does_not_recheck_previous_creator(monkeypatch):
    checked, _, _ = _run_msg_check(monkeypatch, ["a_creator", "onlyfans.com/my/chats"])
    assert checked == [("a_creator", "111")]