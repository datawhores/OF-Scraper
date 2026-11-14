"""Check-table cell shortcuts and inclusive length filters (#419)."""

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import SelectionList

import ofscraper.classes.table.app as table_app


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


@pytest.fixture(autouse=True)
def _stub_settings(monkeypatch):
    monkeypatch.setattr(
        table_app.settings, "get_settings",
        lambda: _Settings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings, "get_args",
        lambda: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app.cache, "get", lambda *a, **k: True)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())


def _row(index, **values):
    row = dict(
        index=index, number=index, download_cart="[]", username="a_creator",
        downloaded=False, unlocked=True, download_type="normal",
        other_posts_with_media=[], length="0:01:30", mediatype="Videos",
        post_date="2024-01-01", post_media_count=1, responsetype="Timeline",
        price="Free", post_id=100 + index, media_id=1000 + index, text="t",
    )
    row.update(values)
    return row


def _drive(rows, steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(run())


def test_username_cell_semicolon_copies_to_filter():
    async def steps(app, pilot):
        app.table.move_cursor(
            row=0, column=app.table.ordered_columns_keys.index("username")
        )
        app.table.focus()
        await pilot.press(";")
        assert app.query_one("#username").value == "a_creator"

    _drive([_row(1)], steps)


@pytest.mark.parametrize(
    "response",
    ["Timeline", "Archived", "Pinned", "Streams", "Stories", "Highlights", "Messages"],
)
def test_response_cell_semicolon_selects_its_option(response):
    async def steps(app, pilot):
        app.table.move_cursor(
            row=0, column=app.table.ordered_columns_keys.index("responsetype")
        )
        app.table.focus()
        await pilot.press(";")
        selected = app.query_one("#responsetype").query_one(SelectionList).selected
        assert selected == [response]

    _drive([_row(1, responsetype=response)], steps)


@pytest.mark.parametrize(
    "start, end, expected",
    [
        ("0:01:00", None, [2, 3, 4, 5]),
        (None, "0:02:00", [1, 2, 3, 4]),
        ("0:01:00", "0:02:00", [2, 3, 4]),
    ],
)
def test_length_filter_includes_bounds(start, end, expected):
    async def steps(app, pilot):
        field = app.query_one("#length")
        if start is not None:
            field.update_table_min(start)
        if end is not None:
            field.update_table_max(end)
        app.set_filtered_rows()
        assert [row["index"] for row in app._filtered_rows] == expected

    rows = [
        _row(index, length=length)
        for index, length in enumerate(
            ["0:00:30", "0:01:00", "0:01:30", "0:02:00", "0:02:30"], 1
        )
    ]
    _drive(rows, steps)
