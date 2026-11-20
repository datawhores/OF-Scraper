"""The per-creator step of the command loop is one method, ``_process_user``,
so a command can replace how one creator is handled (the Fansly
page-by-page download) while the loop keeps its error handling and
progress count."""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.commands.utils.command as command
import ofscraper.utils.logs.utils.level as level


class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def quiet(monkeypatch):
    level.addtraceback()  # the loop logs tracebacks at this level
    advanced = []
    monkeypatch.setattr(command.CommandManager, "_data_helper", lambda *_: None)
    monkeypatch.setattr(command.CommandManager, "_avatar_helper", lambda *_: None)
    monkeypatch.setattr(
        command.progress_updater.activity, "update_user",
        lambda **k: advanced.append(k.get("advance")),
    )
    monkeypatch.setattr(command, "log_user_failure", lambda name, e, what=None: failed.append(name))
    failed = []
    return SimpleNamespace(advanced=advanced, failed=failed)


def users(*names):
    return [SimpleNamespace(name=n) for n in names]


def test_a_subclass_replaces_the_step_for_one_creator(quiet, monkeypatch):
    async def scan(ele, c=None):
        return f"posts of {ele.name}"

    monkeypatch.setattr(command, "post_media_process", scan)
    done = []

    class Manager(command.CommandManager):
        async def _process_user(self, ele, c, action_func):
            if ele.name == "own":
                done.append(("own way", ele.name, c))
                return
            await super()._process_user(ele, c, action_func)

    async def action(ele=None, postcollection=None):
        done.append(("action", ele.name, postcollection))

    session = Session()
    asyncio.run(Manager()._process_users_normal(users("own", "usual"), session, action))
    assert done == [("own way", "own", session), ("action", "usual", "posts of usual")]
    assert quiet.advanced == [1, 1]


def test_the_loop_keeps_handling_failures_of_the_step(quiet):
    class Manager(command.CommandManager):
        async def _process_user(self, ele, c, action_func):
            if ele.name == "first":
                raise ValueError("boom")
            await action_func(ele=ele, postcollection=None)

    done = []

    async def action(ele=None, postcollection=None):
        done.append(ele.name)

    asyncio.run(Manager()._process_users_normal(users("first", "second"), Session(), action))
    assert done == ["second"]
    assert quiet.failed == ["first"]
    assert quiet.advanced == [1, 1]


def test_a_failed_scan_skips_the_action(quiet, monkeypatch):
    async def scan(ele, c=None):
        return None  # the scrape failed and has said so

    monkeypatch.setattr(command, "post_media_process", scan)
    done = []

    async def action(ele=None, postcollection=None):
        done.append(ele.name)

    asyncio.run(command.CommandManager()._process_user(users("a")[0], None, action))
    assert done == []
