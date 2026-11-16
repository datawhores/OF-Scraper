"""Check table: a right-click copies a username or the other posts' ids.

The table is drawn by the app, so the terminal can't select text from it.
A right-click on a cell in the UserName or Other_Posts_With_Media column
copies it to the clipboard and says so. It doesn't select the cell, and a
right-click on any other column is unchanged. These tests drive the real
InputApp.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.coordinate import Coordinate

import ofscraper.classes.table.app as table_app


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _row(index, username):
    return {
        "index": index,
        "number": index,
        "download_cart": "[]",
        "username": username,
        "downloaded": False,
        "unlocked": True,
        "download_type": "normal",
        "other_posts_with_media": [],
        "post_media_count": 1,
        "mediatype": "Videos",
        "post_date": "2024-01-01",
        "media": 1,
        "length": "0:01:30",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": "t",
    }


@pytest.fixture
def start(monkeypatch, tmp_path):
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


async def _settle(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


def _drive(steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = [_row(1, "first_creator"), _row(2, "second_creator")]
        app.table_data[0]["other_posts_with_media"] = [111, 222]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await _settle(pilot)
            notices = []
            app.notify = lambda message, **kwargs: notices.append(message)
            await steps(app, pilot, app.query_one("#media_table"), notices)

    asyncio.run(run())


async def _click(pilot, table, row, column, button, char=None):
    """Click a cell by its place on screen: the middle, or the char-th
    character of its text."""
    region = table._get_cell_region(Coordinate(row, table.ordered_columns_keys.index(column)))
    x = region.width // 2 if char is None else table.cell_padding + char
    assert await pilot.click(table, offset=(region.x + x, region.y), button=button)
    await _settle(pilot)


def test_right_click_copies_the_username(start):
    async def steps(app, pilot, table, notices):
        before = table.cursor_coordinate

        await _click(pilot, table, 1, "username", button=3)

        assert app.clipboard == "second_creator"
        assert notices == ["Copied second_creator"]
        # the cell isn't selected, so the cursor stays where it was
        assert table.cursor_coordinate == before

    _drive(steps)


def test_right_click_copies_other_posts_with_media(start):
    async def steps(app, pilot, table, notices):
        await pilot.press("h")
        await _settle(pilot)
        # the cell shows [111, 222]: a click on an id copies that id
        await _click(pilot, table, 0, "other_posts_with_media", button=3, char=1)
        assert app.clipboard == "111"
        await _click(pilot, table, 0, "other_posts_with_media", button=3, char=8)
        assert app.clipboard == "222"

        # a click between them copies them all, without the brackets
        await _click(pilot, table, 0, "other_posts_with_media", button=3, char=4)
        assert app.clipboard == "111, 222"
        assert notices == ["Copied 111", "Copied 222", "Copied 111, 222"]

        # an empty list has nothing to copy
        await _click(pilot, table, 1, "other_posts_with_media", button=3)
        assert app.clipboard == "111, 222"
        assert len(notices) == 3

    _drive(steps)


def test_right_click_elsewhere_copies_nothing(start):
    async def steps(app, pilot, table, notices):
        await _click(pilot, table, 1, "mediatype", button=3)

        assert app.clipboard == ""
        assert notices == []

    _drive(steps)


def test_left_click_on_a_username_copies_nothing(start):
    async def steps(app, pilot, table, notices):
        await _click(pilot, table, 1, "username", button=1)

        assert app.clipboard == ""
        assert notices == []
        assert table.cursor_coordinate.row == 1

    _drive(steps)
