import asyncio

from textual.widgets import Button, Input

import ofscraper.sites as sites
import ofscraper.utils.console as console_
import ofscraper.utils.events as of_events
import ofscraper.utils.logs.logger as logger
from ofscraper.classes.live_tui.app import LiveStreamApp
from ofscraper.classes.live_tui.state import LiveStore, StreamRowState
from ofscraper.classes.table.sections.table import DataTableExtended
from ofscraper.sites.fansly import live as shared_live


def _patch_env(monkeypatch):
    monkeypatch.setattr(sites, "is_fansly", lambda: True)
    monkeypatch.setattr(
        shared_live,
        "options",
        lambda s=None: {
            "usernames": None,
            "chat": False,
            "max_concurrent": 2,
            "interval": 60,
            "jitter": 0,
        },
    )
    monkeypatch.setattr(logger, "add_widget", lambda *a, **kw: None)
    monkeypatch.setattr(logger, "remove_widget", lambda *a, **kw: None)


async def _idle_runner(watch, stop):
    await stop.wait()


def _visible_usernames(app: LiveStreamApp) -> list[str]:
    table = app.query_one("#streams_table", DataTableExtended)
    return [app._streams[row.key.value].username for row in table.ordered_rows]


def test_live_store_should_show_search_query():
    store = LiveStore()
    rec = StreamRowState(
        key="fansly:101", site="Fansly", account_id="101", username="Alice_Live", status="recording", is_online=True
    )
    off = StreamRowState(
        key="fansly:102", site="Fansly", account_id="102", username="Alice_Idle", status="offline", is_online=False
    )
    assert store.should_show(rec, "online", "@alice") is True
    assert store.should_show(rec, "online", "101") is True
    assert store.should_show(rec, "online", "bob") is False
    assert store.should_show(off, "online", "alice") is False
    assert store.should_show(off, "all", "alice") is True


def test_search_additive_with_filter_modes_and_keys(monkeypatch):
    _patch_env(monkeypatch)
    shared_console = console_.get_shared_console()
    was_quiet = shared_console.quiet

    async def _run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        try:
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                of_events.emit_sync(
                    "live_poll",
                    state="targets",
                    site="fansly",
                    targets=[
                        {"accountId": "101", "username": "alice_live"},
                        {"accountId": "102", "username": "alice_idle"},
                        {"accountId": "203", "username": "bob_live"},
                    ],
                )
                of_events.emit_sync(
                    "live_poll",
                    state="ok",
                    site="fansly",
                    online=[
                        {"accountId": "101", "username": "alice_live"},
                        {"accountId": "203", "username": "bob_live"},
                    ],
                )
                of_events.emit_sync(
                    "live_stream",
                    site="fansly",
                    account_id="101",
                    username="alice_live",
                    status="recording",
                    reason="part1.mp4",
                )
                await pilot.pause()

                assert app._filter_mode == "online"
                assert set(_visible_usernames(app)) == {"alice_live", "bob_live"}

                await pilot.press("slash")
                await pilot.pause()
                assert not app.query_one("#search_bar").has_class("-hidden")
                await pilot.press("f")
                await pilot.pause()
                assert app._filter_mode == "online"
                app.query_one("#search_input", Input).value = "@Alice"
                await pilot.pause()
                assert _visible_usernames(app) == ["alice_live"]

                await pilot.press("enter")
                await pilot.pause()
                assert app.query_one("#search_bar").has_class("-hidden")
                assert "Search: alice (/)" in str(app.query_one("#btn_search", Button).label)

                await pilot.press("f")
                await pilot.pause()
                assert app._filter_mode == "recording"
                assert _visible_usernames(app) == ["alice_live"]

                await pilot.press("f")
                await pilot.pause()
                assert app._filter_mode == "all"
                assert set(_visible_usernames(app)) == {"alice_live", "alice_idle"}

                await pilot.press("slash")
                await pilot.pause()
                app.query_one("#search_input", Input).value = "203"
                await pilot.pause()
                assert _visible_usernames(app) == ["bob_live"]

                await pilot.press("escape")
                await pilot.pause()
                assert app._search_query == ""
                assert app.query_one("#search_bar").has_class("-hidden")
                assert set(_visible_usernames(app)) == {"alice_live", "alice_idle", "bob_live"}
        finally:
            if app._live_thread and app._live_thread.is_alive():
                app._live_thread.stop(timeout=5)
            shared_console.quiet = was_quiet

    asyncio.run(_run())


def test_hidden_row_stream_events_do_not_rebuild_table(monkeypatch):
    _patch_env(monkeypatch)
    shared_console = console_.get_shared_console()
    was_quiet = shared_console.quiet

    async def _run():
        app = LiveStreamApp(watch=True, runner=_idle_runner)
        try:
            async with app.run_test(size=(140, 40)) as pilot:
                await pilot.pause()
                of_events.emit_sync(
                    "live_poll",
                    state="ok",
                    site="fansly",
                    online=[
                        {"accountId": "101", "username": "alice"},
                        {"accountId": "202", "username": "bob"},
                    ],
                )
                await pilot.pause()

                await pilot.press("slash")
                await pilot.pause()
                app.query_one("#search_input", Input).value = "alice"
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                assert _visible_usernames(app) == ["alice"]

                rebuilds = []
                orig_rebuild = app._rebuild_table
                app._rebuild_table = lambda: (rebuilds.append(1), orig_rebuild())

                of_events.emit_sync(
                    "live_stream",
                    site="fansly",
                    account_id="202",
                    username="bob",
                    status="recording",
                    reason="bob_live.mp4",
                )
                of_events.emit_sync(
                    "live_stream",
                    site="fansly",
                    account_id="202",
                    username="bob",
                    status="recording",
                    part_num=2,
                    reason="bob_live_part2.mp4",
                )
                await pilot.pause()
                assert rebuilds == []
        finally:
            if app._live_thread and app._live_thread.is_alive():
                app._live_thread.stop(timeout=5)
            shared_console.quiet = was_quiet

    asyncio.run(_run())
