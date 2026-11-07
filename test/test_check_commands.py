"""Check commands: paid lookups, -f files and msg_check's help (#202)."""

import ast
import asyncio
import contextlib
import pathlib
from types import SimpleNamespace

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


def test_check_usernames_combines_u_and_f(monkeypatch):
    current = SimpleNamespace(check_usernames=["from_u"], file_usernames=["from_f"])
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    assert check.check_usernames() == ["from_u", "from_f"]
    current.check_usernames = None
    assert check.check_usernames() == ["from_f"]


def test_msg_check_help_describes_messages():
    assert message.message_check.name == "msg_check"
    assert "messages" in message.message_check.short_help
    assert "post_check" not in message.message_check.help
