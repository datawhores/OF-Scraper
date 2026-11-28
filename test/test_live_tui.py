"""Unit tests for the interactive Live TUI, LiveWatcher controls, OnlyFans
extra-target polling, synchronous event dispatch, and the ``live_tui`` CLI.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import click
import pytest
from textual.dom import NoActiveAppError
from textual.widgets import Input, RichLog, Static

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.classes.table.utils.open_folder as open_folder
import ofscraper.data.api.subscriptions.individual as individual
import ofscraper.data.api.subscriptions.subscriptions as subscriptions
import ofscraper.managers.manager as manager
import ofscraper.sites as sites
import ofscraper.utils.args.parse.commands.live_tui as live_tui_cmd
import ofscraper.utils.args.parse.commands.main as main_cmd
import ofscraper.utils.console as console_mod
import ofscraper.utils.events as events
import ofscraper.utils.logs.logger as logger_mod
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
from ofscraper.classes.live_tui.app import LiveStreamApp, StreamRowState
from ofscraper.classes.live_tui.compose import LiveConsole
from ofscraper.sites.fansly import live as fansly_live
from ofscraper.sites.onlyfans import live as onlyfans_live


async def _idle_runner(watch, stop):
    await stop.wait()


@pytest.fixture
def tui_env(monkeypatch):
    """Isolate global events, console, logger widgets, and options for TUI tests."""
    monkeypatch.setattr(events, "_subscribers", {})
    monkeypatch.setattr(logger_mod, "add_widget", lambda *a, **k: None)
    monkeypatch.setattr(logger_mod, "remove_widget", lambda *a, **k: None)
    shared_console = console_mod.get_shared_console()
    was_quiet = shared_console.quiet
    monkeypatch.setattr(
        fansly_live,
        "options",
        lambda s=None: {
            "once": False,
            "watch": True,
            "tui": True,
            "interval": 60,
            "max_concurrent": 2,
            "jitter": 0,
            "max_failures": 3,
            "check_concurrency": 5,
            "chat": False,
            "usernames": None,
            "excluded": None,
            "username_search": None,
            "has_filters": False,
        },
    )
    monkeypatch.setattr(sites, "is_fansly", lambda: True)
    yield
    shared_console.quiet = was_quiet


# ------------------------------------------------------------------ LiveStreamApp UI & telemetry


def test_refresh_telemetry_escapes_last_error_markup(tui_env):
    async def run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            # Bracketed errno + closing tag would raise rich.errors.MarkupError if unescaped
            app._last_error = "[Errno 104] Connection reset [/bad]"
            app._refresh_telemetry()
            mid = app.query_one("#telemetry_mid", Static)
            rendered = str(mid.render())
            assert "[Errno 104] Connection reset [/bad]" in rendered
            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


def test_compose_sets_max_lines_on_log_widgets(tui_env):
    async def run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            console_widget = app.query_one("#live_console", LiveConsole)
            chat_widget = app.query_one("#live_chat_log", RichLog)
            assert console_widget.max_lines == 1000
            assert chat_widget.max_lines == 1000
            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


def test_live_console_write_suppresses_no_active_app_error(monkeypatch):
    widget = LiveConsole()
    monkeypatch.setattr(LiveConsole, "is_mounted", property(lambda self: True))
    monkeypatch.setattr(
        LiveConsole,
        "app",
        property(lambda self: (_ for _ in ()).throw(NoActiveAppError("no active app"))),
    )
    assert widget.write("background log during teardown") is widget


def test_action_stop_all_marks_recording_rows_stopping_and_preserves_slot_floor(tui_env):
    async def run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            watcher = MagicMock()
            app._watcher = watcher
            app._watcher_loop = asyncio.get_running_loop()
            app._max_concurrent = 2

            rec_a = StreamRowState(
                key="fansly:1", site="Fansly", account_id="1", username="creator_a",
                status="recording", is_online=True,
            )
            rec_b = StreamRowState(
                key="fansly:2", site="Fansly", account_id="2", username="creator_b",
                status="recording", is_online=True,
            )
            queued_c = StreamRowState(
                key="fansly:3", site="Fansly", account_id="3", username="creator_c",
                status="queued", is_online=True,
            )
            app._streams = {"fansly:1": rec_a, "fansly:2": rec_b, "fansly:3": queued_c}

            app.action_stop_all()

            assert rec_a.status == "stopping"
            assert rec_b.status == "stopping"
            assert queued_c.status == "stopped"

            # Both actively recording rows are still flushing ("stopping"), so
            # Slots - must not drop below 2.
            app.action_slots_down()
            assert app._max_concurrent == 2

            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


def test_action_toggle_following_handles_none_extra_and_prunes_index(tui_env):
    async def run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            watcher = SimpleNamespace(
                include_following=True,
                extra_usernames=None,
                set_include_following=MagicMock(),
            )
            app._watcher = watcher
            app._watcher_loop = asyncio.get_running_loop()
            app._include_following = True

            offline = StreamRowState(
                key="fansly:10", site="Fansly", account_id="10", username="creator_off",
                status="offline", is_online=False,
            )
            app._streams = {"fansly:10": offline}
            app._username_index = {("fansly", "creator_off"): "fansly:10"}

            app.action_toggle_following()

            assert "fansly:10" not in app._streams
            assert ("fansly", "creator_off") not in app._username_index
            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


def test_open_entry_folder_uses_live_recording_path(tui_env, tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_live" / "creator_a"
    custom_dir.mkdir(parents=True)
    expected_file = custom_dir / "creator_a_20260101_000000_live.mp4"

    monkeypatch.setattr(common_paths, "get_save_location", lambda config=None: str(tmp_path))
    monkeypatch.setattr(
        placeholder,
        "live_recording_path",
        lambda save_loc, username, started_at, **kw: expected_file,
    )
    opened = []
    monkeypatch.setattr(open_folder, "open_target", lambda target: opened.append(target))

    async def run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            entry = StreamRowState(
                key="fansly:10", site="Fansly", account_id="10", username="creator_a",
                status="online", is_online=True,
            )
            app._open_entry_folder(entry)
            assert len(opened) == 1
            assert opened[0].folder == custom_dir.resolve()
            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


# ------------------------------------------------------------------ Remove & re-add creator


def test_remove_and_readd_creator_in_watcher_and_app(tui_env):
    async def run():
        async def fetch_online():
            return []

        async def record(stream, stop_event):
            pass

        watcher = fansly_live.LiveWatcher(fetch_online, record, site="fansly")

        # Direct LiveWatcher remove -> add cycle
        watcher.remove_username("Creator_A", account_id="12345")
        assert "creator_a" in watcher.excluded_usernames
        assert "12345" in watcher.excluded_usernames
        assert "12345" in watcher.suppressed

        watcher.add_usernames(["creator_a"])
        assert "creator_a" in watcher.extra_usernames
        assert "creator_a" not in watcher.excluded_usernames
        assert "12345" not in watcher.excluded_usernames
        assert "12345" not in watcher.suppressed

        # Full LiveStreamApp remove -> re-add cycle
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            app._watcher = watcher
            app._watcher_loop = asyncio.get_running_loop()

            app._handle_poll({
                "state": "ok",
                "site": "fansly",
                "online": [{"accountId": "12345", "username": "Creator_A"}],
            })
            assert "fansly:12345" in app._streams

            app._remove_entry(app._streams["fansly:12345"])
            await asyncio.sleep(0)
            assert "fansly:12345" in app._removed_keys
            assert "fansly:12345" not in app._streams
            assert "12345" in watcher.excluded_usernames
            assert "12345" in watcher.suppressed

            inp = app.query_one("#add_user_input", Input)
            inp.value = "Creator_A"
            app._submit_add_user()
            await asyncio.sleep(0)

            assert "fansly:12345" not in app._removed_keys
            assert "12345" not in watcher.excluded_usernames
            assert "12345" not in watcher.suppressed

            # Subsequent poll event for the same accountId must re-populate the row
            app._handle_poll({
                "state": "ok",
                "site": "fansly",
                "online": [{"accountId": "12345", "username": "Creator_A"}],
            })
            assert "fansly:12345" in app._streams

            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


# ------------------------------------------------------------------ LiveWatcher pause & resume_all


def test_live_watcher_paused_does_not_start_queued_recordings(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})

    async def run():
        started = []
        first_started = asyncio.Event()
        finish_first = asyncio.Event()
        streams = [
            {"accountId": "p1", "username": "creator_1"},
            {"accountId": "p2", "username": "creator_2"},
        ]

        async def fetch_online():
            return list(streams)

        async def record(stream, stop_event):
            started.append(stream["accountId"])
            if stream["accountId"] == "p1":
                first_started.set()
                await finish_first.wait()
            else:
                await stop_event.wait()

        stop = asyncio.Event()
        watcher = fansly_live.LiveWatcher(
            fetch_online, record, max_concurrent=1, interval=60, jitter=0, site="fansly"
        )
        task = asyncio.create_task(watcher.run(stop))
        try:
            await asyncio.wait_for(first_started.wait(), timeout=2.0)
            assert started == ["p1"]

            # Pause polls, then let p1 finish so a slot frees up
            watcher.set_paused(True)
            finish_first.set()
            await asyncio.sleep(0.1)

            # Queued stream p2 must NOT start while paused
            assert started == ["p1"]
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=2.0)

    asyncio.run(run())


def test_live_watcher_resume_all_does_not_unsuppress_removed_creators(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})
    emitted = []
    events.subscribe("live_stream", lambda **kw: emitted.append(kw))

    async def fetch_online():
        return []

    async def record(stream, stop_event):
        pass

    watcher = fansly_live.LiveWatcher(fetch_online, record, site="fansly")
    watcher._last_online["111"] = {"accountId": "111", "username": "stopped_user"}
    watcher._last_online["222"] = {"accountId": "222", "username": "removed_user"}

    watcher.stop_creator("111")
    watcher.remove_username("removed_user", account_id="222")
    emitted.clear()

    watcher.resume_all()

    assert "111" not in watcher.suppressed
    assert "222" in watcher.suppressed
    assert "222" in watcher.excluded_usernames
    assert "removed_user" in watcher.excluded_usernames
    resumed_ids = [e["account_id"] for e in emitted if e.get("status") == "queued"]
    assert resumed_ids == ["111"]


@pytest.mark.parametrize("still_live", [True, False])
def test_live_watcher_readd_by_account_id_forgets_the_removed_name(monkeypatch, still_live):
    """A creator removed from the watch and added back by account id was still
    left out by the username the removal recorded, so never recorded again."""
    monkeypatch.setattr(events, "_subscribers", {})

    async def fetch_online():
        return []

    async def record(stream, stop_event):
        pass

    watcher = fansly_live.LiveWatcher(fetch_online, record, site="fansly")
    watcher._last_online["123"] = {"accountId": "123", "username": "Alice"}
    watcher.remove_username("Alice", account_id="123")
    if not still_live:
        # a poll that no longer finds the creator live forgets the stop
        watcher.suppressed.clear()

    watcher.add_usernames(["123"])

    assert watcher.excluded_usernames == set()
    assert watcher._removed_ids == {}
    assert "123" not in watcher.suppressed
    stream = {"accountId": "123", "username": "Alice"}
    assert fansly_live.select_streams([stream], None, watcher.excluded_usernames) == [stream]


def test_live_watcher_readd_by_account_id_keeps_other_removed_creators(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})

    async def fetch_online():
        return []

    async def record(stream, stop_event):
        pass

    watcher = fansly_live.LiveWatcher(fetch_online, record, site="fansly")
    watcher.remove_username("Alice", account_id="123")
    watcher.remove_username("Bob", account_id="456")

    watcher.add_usernames(["123"])

    assert watcher.excluded_usernames == {"bob", "456"}
    assert watcher._removed_ids == {"bob": {"456"}}
    assert watcher.suppressed == {"456"}


def test_live_watcher_readd_while_the_old_recording_closes_restarts_at_once(monkeypatch):
    """Removing a creator stops their recording, which takes a moment to
    close. Added back meanwhile, they are recorded again as soon as it has
    closed, not on the next interval (a minute or more of the stream)."""
    monkeypatch.setattr(events, "_subscribers", {})

    async def run():
        starts = []
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        closed = asyncio.Event()

        async def fetch_online():
            return [{"accountId": "readd-7", "username": "alice"}]

        async def record(stream, stop_event):
            starts.append(stream["accountId"])
            if len(starts) == 1:
                first_started.set()
                await stop_event.wait()
                await closed.wait()
            else:
                second_started.set()
                await stop_event.wait()

        stop = asyncio.Event()
        watcher = fansly_live.LiveWatcher(
            fetch_online, record, max_concurrent=1, interval=60, jitter=0, site="fansly"
        )
        task = asyncio.create_task(watcher.run(stop))
        try:
            await asyncio.wait_for(first_started.wait(), timeout=2.0)

            watcher.remove_username("alice", account_id="readd-7")
            await asyncio.sleep(0.05)
            watcher.add_usernames(["alice"])
            # the check add_usernames asks for runs while the recording closes
            await asyncio.sleep(0.05)
            assert starts == ["readd-7"]

            closed.set()
            await asyncio.wait_for(second_started.wait(), timeout=2.0)
            assert starts == ["readd-7", "readd-7"]
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=2.0)

    asyncio.run(run())


def test_live_watcher_paused_queue_says_it_is_paused(monkeypatch):
    """While polls are paused a waiting creator isn't short of a recording
    slot: the row says the pause is what holds it."""
    monkeypatch.setattr(events, "_subscribers", {})
    emitted = []
    events.subscribe("live_stream", lambda **kw: emitted.append(kw))

    async def run():
        async def fetch_online():
            return [{"accountId": "paused-1", "username": "creator_1"}]

        async def record(stream, stop_event):
            await stop_event.wait()

        stop = asyncio.Event()
        watcher = fansly_live.LiveWatcher(
            fetch_online, record, max_concurrent=2, interval=60, jitter=0, site="fansly"
        )
        watcher.paused = True
        task = asyncio.create_task(watcher.run(stop))
        try:
            await asyncio.sleep(0.1)
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=2.0)

    asyncio.run(run())

    reasons = [e["reason"] for e in emitted if e.get("status") == "queued"]
    assert reasons == ["Polls paused; starts when resumed"]


def test_app_readd_by_account_id_forgets_the_removed_username(tui_env):
    async def run():
        async def fetch_online():
            return []

        async def record(stream, stop_event):
            pass

        watcher = fansly_live.LiveWatcher(fetch_online, record, site="fansly")
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        async with app.run_test():
            app._watcher = watcher
            app._watcher_loop = asyncio.get_running_loop()
            app._handle_poll({
                "state": "ok",
                "site": "fansly",
                "online": [{"accountId": "12345", "username": "Creator_A"}],
            })
            app._remove_entry(app._streams["fansly:12345"])
            await asyncio.sleep(0)
            assert app._removed_user_ids == {("fansly", "creator_a"): "12345"}

            app.query_one("#add_user_input", Input).value = "12345"
            app._submit_add_user()
            await asyncio.sleep(0)

            assert app._removed_keys == set()
            assert app._removed_user_ids == {}
            assert watcher.excluded_usernames == set()
            assert "12345" not in watcher.suppressed

            if app._live_thread:
                app._live_thread.stop(timeout=5)

    asyncio.run(run())


# ------------------------------------------------------------------ OnlyFans get_online_streams


class _FakeResponse:
    def __init__(self, status, data=None):
        self.status = status
        self.data = data

    async def json_(self):
        return self.data


class _FakeSession:
    def __init__(self, active_by_user):
        self.active_by_user = active_by_user
        self.checked_urls = []

    def requests_async(self, url=None, **kwargs):
        self.checked_urls.append(url)
        user = next((u for u in self.active_by_user if f"/{u}/" in (url or "")), None)
        is_active = self.active_by_user.get(user, False)

        class _Ctx:
            async def __aenter__(self_inner):
                return _FakeResponse(200, {"isActive": is_active})

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


def test_onlyfans_get_online_streams_all_users_with_filters_and_extra(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})
    poll_targets = []
    events.subscribe(
        "live_poll",
        lambda **kw: poll_targets.append(kw["targets"]) if kw.get("state") == "targets" else None,
    )

    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            usernames=None,
            excluded_username=None,
            username_search=None,
            blacklist=None,
            userlist=["vip"],
            live_watch=True,
        ),
    )
    monkeypatch.setattr(
        onlyfans_live.shared,
        "options",
        lambda s=None: {
            "usernames": None,
            "excluded": None,
            "username_search": None,
        },
    )
    monkeypatch.setattr(onlyfans_live.shared, "has_custom_user_filters", lambda s=None: True)

    async def fake_list_members(names):
        return []

    async def fake_active_helper(_a, _c, strict=True):
        return [{"id": 1, "username": "sub_creator", "hasStream": False}]

    async def fake_expired_helper(_a, _c, strict=True):
        return []

    async def fake_scrape_active(_c, strict=False):
        yield [{"id": 1, "username": "sub_creator", "hasStream": False}]

    async def fake_get_subscription(names):
        return [
            {"id": 99, "username": "extra_creator", "hasStream": True}
            for n in names
            if n.lower() == "extra_creator"
        ]

    monkeypatch.setattr(onlyfans_live, "_list_members", fake_list_members)
    monkeypatch.setattr(subscriptions, "activeHelper", fake_active_helper)
    monkeypatch.setattr(subscriptions, "expiredHelper", fake_expired_helper)
    monkeypatch.setattr(subscriptions, "scrape_subscriptions_active", fake_scrape_active)
    monkeypatch.setattr(individual, "get_subscription", fake_get_subscription)
    monkeypatch.setattr(
        manager,
        "Manager",
        SimpleNamespace(
            model_manager=SimpleNamespace(
                filter_models=lambda models: [m for m in models if m.name == "sub_creator"]
            )
        ),
    )

    watcher = SimpleNamespace(
        include_following=True,
        extra_usernames={"extra_creator"},
        excluded_usernames=set(),
    )
    c = _FakeSession({"sub_creator": False, "extra_creator": True})

    cache_tok = onlyfans_live._TARGET_CACHE.set({})
    watcher_tok = onlyfans_live._WATCHER.set(watcher)
    try:
        result = asyncio.run(onlyfans_live.get_online_streams(c, checks=c))
    finally:
        onlyfans_live._WATCHER.reset(watcher_tok)
        onlyfans_live._TARGET_CACHE.reset(cache_tok)

    assert any(r["username"] == "extra_creator" for r in result)
    assert poll_targets
    emitted_names = {t["username"] for t in poll_targets[-1]}
    assert "extra_creator" in emitted_names
    assert "sub_creator" in emitted_names


def test_onlyfans_get_online_streams_all_users_no_filters_caches_extra(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            usernames=None,
            excluded_username=None,
            username_search=None,
            blacklist=None,
            live_watch=True,
        ),
    )
    monkeypatch.setattr(
        onlyfans_live.shared,
        "options",
        lambda s=None: {
            "usernames": None,
            "excluded": None,
            "username_search": None,
        },
    )
    monkeypatch.setattr(onlyfans_live.shared, "has_custom_user_filters", lambda s=None: False)

    async def fake_list_members(names):
        return []

    async def fake_scrape_active(_c, strict=False):
        yield []

    lookup_calls = []

    async def fake_get_subscription(names):
        lookup_calls.append(list(names))
        return [
            {"id": 77, "username": "extra_one", "hasStream": False}
            for n in names
            if n.lower() == "extra_one"
        ]

    monkeypatch.setattr(onlyfans_live, "_list_members", fake_list_members)
    monkeypatch.setattr(subscriptions, "scrape_subscriptions_active", fake_scrape_active)
    monkeypatch.setattr(individual, "get_subscription", fake_get_subscription)

    watcher = SimpleNamespace(
        include_following=True,
        extra_usernames={"extra_one"},
        excluded_usernames=set(),
    )
    c = _FakeSession({"extra_one": True})

    cache_tok = onlyfans_live._TARGET_CACHE.set({})
    watcher_tok = onlyfans_live._WATCHER.set(watcher)
    try:
        res1 = asyncio.run(onlyfans_live.get_online_streams(c, checks=c))
        res2 = asyncio.run(onlyfans_live.get_online_streams(c, checks=c))
    finally:
        onlyfans_live._WATCHER.reset(watcher_tok)
        onlyfans_live._TARGET_CACHE.reset(cache_tok)

    assert [r["username"] for r in res1] == ["extra_one"]
    assert [r["username"] for r in res2] == ["extra_one"]
    # Individual lookup must be cached across polls when extra/excluded did not change
    assert len(lookup_calls) == 1


# ------------------------------------------------------------------ events.emit_sync


def test_emit_sync_dispatches_sync_isolates_errors_and_closes_async(monkeypatch, caplog):
    monkeypatch.setattr(events, "_subscribers", {})
    received = []
    async_ran = []

    def failing_sub(**kw):
        raise RuntimeError("subscriber boom")

    async def async_sub(**kw):
        async_ran.append(kw)

    def good_sub(**kw):
        received.append(kw)

    events.subscribe("live_stream", failing_sub)
    events.subscribe("live_stream", async_sub)
    events.subscribe("live_stream", good_sub)

    with caplog.at_level(logging.DEBUG, logger="shared"):
        events.emit_sync("live_stream", username="creator_a", status="recording")

    assert received == [{"username": "creator_a", "status": "recording"}]
    assert async_ran == []
    assert any("skipped in emit_sync" in r.message for r in caplog.records)
    assert any("subscriber boom" in r.message for r in caplog.records)


# ------------------------------------------------------------------ live_tui CLI command


def test_live_tui_cli_sets_flags_and_rejects_no_rich():
    # the program may already have the command: adding it twice raises
    if "live_tui" not in main_cmd.program.commands:
        main_cmd.program.add_command(live_tui_cmd.live_tui, "live_tui")

    params, _ = main_cmd.program(standalone_mode=False, prog_name="OF-Scraper", args=["live_tui"])
    assert params["live_tui"] is True
    assert params["live_watch"] is True
    assert params["live"] is False

    params_once, _ = main_cmd.program(
        standalone_mode=False, prog_name="OF-Scraper", args=["live_tui", "--once"]
    )
    assert params_once["live_tui"] is True
    assert params_once["live_watch"] is False
    assert params_once["live"] is True

    # the watch options added since: off unless given
    assert params["live_jitter"] is None
    assert params["refresh_users"] is False
    params_watch, _ = main_cmd.program(
        standalone_mode=False,
        prog_name="OF-Scraper",
        args=["live_tui", "--live-jitter", "2.5", "--refresh-users"],
    )
    assert params_watch["live_jitter"] == 2.5
    assert params_watch["refresh_users"] is True

    with pytest.raises(click.UsageError, match="no-rich"):
        main_cmd.program(
            standalone_mode=False, prog_name="OF-Scraper", args=["--no-rich", "live_tui"]
        )

    with pytest.raises(click.UsageError, match="no-rich"):
        main_cmd.program(
            standalone_mode=False, prog_name="OF-Scraper", args=["live_tui", "--no-rich"]
        )


def test_live_tui_cli_keeps_runtime_option_groups():
    param_names = {p.name for p in live_tui_cmd.live_tui.params}
    for required in (
        "username_search",
        "dynamic_rules",
        "auth_fail",
        "no_cache",
        "no_api_cache",
        "update_profile",
        "desc",
    ):
        assert required in param_names


def test_live_store_stop_resume_and_index_pruning():
    from ofscraper.classes.live_tui.state import LiveStore

    store = LiveStore()
    store.apply_poll_ok(
        "fansly",
        [
            {"accountId": "1", "username": "creator_a"},
            {"accountId": "2", "username": "creator_b"},
        ],
    )
    store.streams["fansly:1"].status = "recording"

    stopped = store.stop_all()
    assert len(stopped) == 2
    assert store.streams["fansly:1"].status == "stopping"
    assert store.streams["fansly:1"].reason == "Finalizing recording..."
    assert store.streams["fansly:2"].status == "stopped"

    resumed = store.resume_all()
    assert len(resumed) == 2
    assert all(e.status == "queued" and not e.user_stopped for e in resumed)

    store.streams["fansly:2"].status = "ended"
    assert store.clear_ended() == 1
    assert "fansly:2" not in store.streams
    assert ("fansly", "creator_b") not in store.username_index
    assert ("fansly", "creator_a") in store.username_index


def test_formatters_epoch_seconds_and_helpers():
    import datetime

    from ofscraper.classes.live_tui.formatters import _epoch_seconds, _fmt_bytes, _fmt_hms

    assert _epoch_seconds(None) is None
    assert _epoch_seconds("") is None
    assert _epoch_seconds(0) is None
    assert _epoch_seconds(-10) is None
    assert _epoch_seconds(float("inf")) is None
    assert _epoch_seconds(float("-inf")) is None
    assert _epoch_seconds(float("nan")) is None
    assert _epoch_seconds("not-a-date") is None
    assert _epoch_seconds(1_700_000_000) == pytest.approx(1_700_000_000.0)
    assert _epoch_seconds(1_700_000_000_000) == pytest.approx(1_700_000_000.0)
    dt = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    assert _epoch_seconds(dt) == pytest.approx(dt.timestamp())
    assert _epoch_seconds("2026-01-01T00:00:00+00:00") == pytest.approx(dt.timestamp())
    assert _fmt_bytes(0) == "0 B"
    assert _fmt_bytes(1536) == "1.5 KB"
    assert _fmt_hms(3661) == "1:01:01"

