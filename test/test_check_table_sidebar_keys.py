"""Check table: Ctrl+S / Ctrl+D and focus when a sidebar closes (#422).

Textual's Input binds Ctrl+D to "delete character right", so with a sidebar
text box focused Ctrl+D never reached the app. And closing a sidebar could
leave focus on a hidden widget inside it, after which Ctrl+D did nothing,
typing went to hidden filter boxes and the cart keys stopped working.
These tests drive the real InputApp headless with made-up rows.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest

import ofscraper.classes.table.app as table_app


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _row(index):
    return {
        "index": index,
        "number": index,
        "download_cart": "[]",
        "username": "a_creator",
        "downloaded": False,
        "unlocked": True,
        "download_type": "normal",
        "other_posts_with_media": [],
        "post_media_count": 1,
        "mediatype": "Videos",
        "post_date": "2024-01-01",
        "media": 1,
        "length": "0:01:00",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": "t",
    }


@pytest.fixture(autouse=True)
def _stub_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())


def _drive(steps):
    """Run steps(app, pilot) against a headless InputApp with three rows."""

    async def run():
        app = table_app.InputApp()
        app.table_data = [_row(1), _row(2), _row(3)]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(run())


async def _settle(pilot):
    # let Textual handle the Hide events and any focus changes they cause
    for _ in range(5):
        await pilot.pause(0.02)


def _open(app, sidebar_id):
    return app.query_one(f"#{sidebar_id}").has_class("-show")


def _in(app, sidebar_id):
    focused = app.focused
    return focused is not None and app.query_one(f"#{sidebar_id}") in (
        focused.ancestors
    )


def _cart(app):
    return [row["index"] for row in app.table_data if row["download_cart"] == "[added]"]


def test_ctrl_d_closes_the_download_sidebar_from_its_size_box():
    async def steps(app, pilot):
        await pilot.press("ctrl+d")
        await _settle(pilot)
        assert _open(app, "download_option_sidebar")
        app.query_one("#download_size_max_input").focus()
        await _settle(pilot)

        await pilot.press("ctrl+d")
        await _settle(pilot)
        assert not _open(app, "download_option_sidebar")
        assert app.focused is app.table

    _drive(steps)


def test_ctrl_d_switches_sidebars_from_the_text_search_box():
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        app.query_one("#text_search").focus()
        await _settle(pilot)

        await pilot.press("ctrl+d")
        await _settle(pilot)
        assert not _open(app, "options_sidebar")
        assert _open(app, "download_option_sidebar")
        assert not _in(app, "options_sidebar")

    _drive(steps)


@pytest.mark.parametrize(
    "widget", ["#min_hour", "#min_minute", "#min_second", "#text_search"]
)
def test_closing_the_options_sidebar_moves_focus_to_the_table(widget):
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        app.query_one(widget).focus()
        await _settle(pilot)

        await pilot.press("ctrl+s")
        await _settle(pilot)
        assert not _open(app, "options_sidebar")
        assert app.focused is app.table

        # the cart keys reach the app again
        await pilot.press("a")
        await _settle(pilot)
        assert _cart(app) == [1, 2, 3]
        await pilot.press("x")
        await _settle(pilot)
        assert _cart(app) == []

        # and so does the next Ctrl+D
        await pilot.press("ctrl+d")
        await _settle(pilot)
        assert _open(app, "download_option_sidebar")

    _drive(steps)


def test_ctrl_s_from_the_download_sidebar_moves_focus_out_of_it():
    async def steps(app, pilot):
        await pilot.press("ctrl+d")
        await _settle(pilot)
        app.query_one("#download_size_min_input").focus()
        await _settle(pilot)

        # Ctrl+S hides the download sidebar and shows the options one
        await pilot.press("ctrl+s")
        await _settle(pilot)
        assert not _open(app, "download_option_sidebar")
        assert _open(app, "options_sidebar")
        assert app.focused is app.table

        await pilot.press("ctrl+s")
        await _settle(pilot)
        await pilot.press("ctrl+d")
        await _settle(pilot)
        assert _open(app, "download_option_sidebar")

    _drive(steps)


@pytest.mark.parametrize("button", ["#filter", "#filter2"])
def test_the_filter_button_closes_the_sidebar_and_moves_focus_out(button):
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        app.query_one(button).focus()
        await _settle(pilot)

        await pilot.press("enter")
        await _settle(pilot)
        assert not _open(app, "options_sidebar")
        assert app.focused is app.table
        await pilot.press("ctrl+d")
        await _settle(pilot)
        assert _open(app, "download_option_sidebar")

    _drive(steps)
