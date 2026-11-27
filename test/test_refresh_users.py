import asyncio
import contextlib
import types
import cloup as click
import pytest
from click.testing import CliRunner

import ofscraper.data.models.utils.retriver as retriver
import ofscraper.managers.manager as manager
import ofscraper.prompts.prompts as prompts
import ofscraper.sites as sites
import ofscraper.sites.fansly.live as fansly_live
import ofscraper.sites.fansly.live_api as fansly_live_api
import ofscraper.sites.fansly.scrape as fansly_scrape
import ofscraper.sites.onlyfans.live as of_live
import ofscraper.utils.settings as settings
import ofscraper.utils.system.ffmpeg as ffmpeg_finder
from ofscraper.classes.of.models import Model
from ofscraper.managers.model import ModelManager
from ofscraper.utils.args.parse.groups.automatic import (
    automatic_options_tuple,
    refresh_users_option,
)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def test_refresh_users_cli_aliases():
    assert refresh_users_option in automatic_options_tuple

    @click.command()
    @refresh_users_option
    def cli(refresh_users):
        click.echo(str(refresh_users))

    runner = CliRunner()
    assert runner.invoke(cli, []).output.strip() == "False"
    for flag in ("--refresh-users", "--live-pull", "--daemon-pull"):
        res = runner.invoke(cli, [flag])
        assert res.exit_code == 0
        assert res.output.strip() == "True"


def test_daemon_refresh_users_adds_new_subs_and_drops_unsubs(monkeypatch, event_loop):
    orig_args = settings.get_args(copy=True)
    fetch_calls = 0
    passes = iter(
        [
            [Model({"id": 1, "username": "alice", "subscribedBy": True})],
            [
                Model({"id": 1, "username": "alice", "subscribedBy": True}),
                Model({"id": 2, "username": "bob", "subscribedBy": True}),
            ],
            [Model({"id": 2, "username": "bob", "subscribedBy": True})],
        ]
    )

    async def fake_get_models(all_main_models=False):
        nonlocal fetch_calls
        fetch_calls += 1
        return next(passes)

    monkeypatch.setattr(retriver, "get_models", fake_get_models)

    args = settings.get_args(copy=True)
    args.daemon = 5.0
    args.refresh_users = True
    args.actions = ["download"]
    args.usernames = []
    settings.update_args(args)

    try:
        mm = ModelManager()

        mm.prepare_scraper_activity()
        assert [m.name for m in mm.get_scrape_selected_models()] == ["alice"]

        mm.prepare_scraper_activity()
        assert [m.name for m in mm.get_scrape_selected_models()] == ["alice", "bob"]

        mm.prepare_scraper_activity()
        assert [m.name for m in mm.get_scrape_selected_models()] == ["bob"]
        assert fetch_calls == 3
    finally:
        settings.update_args(orig_args)


def test_interactive_repeat_passes_refresh_users_without_reset_prompt(monkeypatch, event_loop):
    """Non-daemon repeat passes (action / prompt modes) also re-fetch subs and
    skip the reset_username_prompt() dialog when --refresh-users is enabled."""
    orig_args = settings.get_args(copy=True)
    passes = iter(
        [
            [Model({"id": 1, "username": "alice", "subscribedBy": True})],
            [
                Model({"id": 1, "username": "alice", "subscribedBy": True}),
                Model({"id": 2, "username": "bob", "subscribedBy": True}),
            ],
            [Model({"id": 2, "username": "bob", "subscribedBy": True})],
        ]
    )

    async def fake_get_models(all_main_models=False):
        return next(passes)

    def fail_if_prompted():
        raise AssertionError("reset_username_prompt should not run with --refresh-users")

    monkeypatch.setattr(retriver, "get_models", fake_get_models)
    monkeypatch.setattr(prompts, "reset_username_prompt", fail_if_prompted)

    args = settings.get_args(copy=True)
    args.daemon = None
    args.refresh_users = True
    args.actions = ["download"]
    args.usernames = ["ALL"]
    settings.update_args(args)

    try:
        mm = ModelManager()

        mm.prepare_scraper_activity()
        assert [m.name for m in mm.get_scrape_selected_models()] == ["alice"]

        mm.prepare_scraper_activity()
        assert [m.name for m in mm.get_scrape_selected_models()] == ["alice", "bob"]

        mm.prepare_scraper_activity()
        assert [m.name for m in mm.get_scrape_selected_models()] == ["bob"]
    finally:
        settings.update_args(orig_args)


def test_onlyfans_live_refresh_users_reloads_cached_targets(monkeypatch):
    orig_args = settings.get_args(copy=True)

    async def fake_fetch_models(c, cache, names=None):
        return [Model({"id": 2, "username": "new_creator", "hasStream": True})]

    async def fake_still_live(c, username):
        return True

    monkeypatch.setattr(of_live, "_fetch_models", fake_fetch_models)
    monkeypatch.setattr(of_live, "still_live", fake_still_live)

    def seeded_cache():
        return {
            "targets": {1: {"accountId": 1, "username": "old_creator"}},
            "unresolved": [],
            "blacklist_ids": set(),
            "named_ids": set(),
        }

    args = settings.get_args(copy=True)
    args.usernames = ["new_creator"]
    args.refresh_users = False
    settings.update_args(args)

    token = of_live._TARGET_CACHE.set(seeded_cache())
    try:
        streams = asyncio.run(of_live.get_online_streams(c=None))
        assert [s["username"] for s in streams] == ["old_creator"]
    finally:
        of_live._TARGET_CACHE.reset(token)

    args.refresh_users = True
    settings.update_args(args)
    token = of_live._TARGET_CACHE.set(seeded_cache())
    try:
        streams = asyncio.run(of_live.get_online_streams(c=None))
        assert [s["username"] for s in streams] == ["new_creator"]
    finally:
        of_live._TARGET_CACHE.reset(token)
        settings.update_args(orig_args)


def test_fansly_live_refresh_users_clears_filter_cache_between_polls(monkeypatch):
    orig_args = settings.get_args(copy=True)
    poll_results = []
    eligible = [False]

    @contextlib.asynccontextmanager
    async def fake_session(*args, **kwargs):
        yield object()

    async def fake_online_streams(c):
        return [{"accountId": "10", "username": "fansly_creator"}]

    async def fake_fansly_get_models(usernames=None, c=None):
        return [{"id": 10, "username": "fansly_creator"}]

    def fake_filter_models(self, models):
        return list(models) if eligible[0] else []

    class TwoPollWatcher:
        def __init__(self, fetch_online, record, **kwargs):
            self.fetch_online = fetch_online

        async def run(self, stop=None):
            poll_results.append(await self.fetch_online())
            eligible[0] = True
            poll_results.append(await self.fetch_online())

    monkeypatch.setattr(sites, "is_fansly", lambda: True)
    monkeypatch.setattr(
        manager,
        "Manager",
        types.SimpleNamespace(
            session=types.SimpleNamespace(aget_ofsession=fake_session),
            model_manager=None,
        ),
    )
    monkeypatch.setattr(fansly_live_api, "get_online_streams", fake_online_streams)
    monkeypatch.setattr(fansly_scrape, "get_models", fake_fansly_get_models)
    monkeypatch.setattr(ModelManager, "filter_models", fake_filter_models)
    monkeypatch.setattr(fansly_live, "LiveWatcher", TwoPollWatcher)
    monkeypatch.setattr(ffmpeg_finder, "get_ffmpeg", lambda: "ffmpeg")

    args = settings.get_args(copy=True)
    args.live_watch = True
    args.sub_status = True
    args.usernames = []
    args.refresh_users = True
    settings.update_args(args)

    try:
        asyncio.run(fansly_live.run(watch=True))
        assert poll_results[0] == []
        assert [s["username"] for s in poll_results[1]] == ["fansly_creator"]
    finally:
        settings.update_args(orig_args)
