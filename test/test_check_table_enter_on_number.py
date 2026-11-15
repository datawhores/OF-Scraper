"""Check table: Enter on the Number cell works like Enter on the Download cell.

On the main table it adds the row to the cart (or takes it out again); on
the cart table it removes the row. These tests drive the real InputApp
headless with made-up rows.
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


def _row(index, unlocked=True):
    return {
        "index": index,
        "number": index,
        "download_cart": "[]",
        "username": "a_creator",
        "downloaded": False,
        "unlocked": unlocked,
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


def _drive(rows, steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(run())


async def _settle(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


def _cart(app):
    return [r["index"] for r in app.table_data if r["download_cart"] == "[added]"]


async def _enter_on(pilot, table, row, column):
    table.focus()
    table.cursor_coordinate = Coordinate(row, table.ordered_columns_keys.index(column))
    await _settle(pilot)
    await pilot.press("enter")
    await _settle(pilot)


def _cell(table, row, column):
    value = table.get_cell_at(Coordinate(row, table.ordered_columns_keys.index(column)))
    return getattr(value, "plain", value)


@pytest.mark.parametrize("column", ["number", "download_cart"])
def test_enter_on_the_main_table_adds_and_removes_the_row(column):
    async def steps(app, pilot):
        table = app.table
        await _enter_on(pilot, table, 1, column)
        assert _cart(app) == [2]
        # the Download cell shows it, whichever cell was pressed
        assert _cell(table, 1, "download_cart") == "[added]"
        assert _cell(table, 1, "number") in (2, "2")

        await _enter_on(pilot, table, 1, column)
        assert _cart(app) == []
        assert _cell(table, 1, "download_cart") == "[]"

    _drive([_row(1), _row(2), _row(3)], steps)


def test_enter_on_number_skips_locked_media_like_the_download_cell():
    async def steps(app, pilot):
        await _enter_on(pilot, app.table, 0, "number")
        assert _cart(app) == []

    _drive([_row(1, unlocked=False)], steps)


@pytest.mark.parametrize("column", ["number", "download_cart"])
def test_enter_on_the_cart_table_removes_the_row(column):
    async def steps(app, pilot):
        await pilot.press("a")  # add the page
        await _settle(pilot)
        assert _cart(app) == [1, 2]
        await pilot.click("#cart")
        await _settle(pilot)
        cart_table = app.query_one("#cart_data_table")
        assert cart_table.row_count == 2

        await _enter_on(pilot, cart_table, 0, column)

        assert len(_cart(app)) == 1
        assert cart_table.row_count == 1

    _drive([_row(1), _row(2)], steps)


def test_enter_on_another_column_does_not_change_the_cart():
    async def steps(app, pilot):
        await _enter_on(pilot, app.table, 0, "username")
        assert _cart(app) == []

    _drive([_row(1)], steps)
