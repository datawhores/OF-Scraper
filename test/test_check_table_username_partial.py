"""Check table filter sidebar (Ctrl+S): the username box matches part of a name.

It only matched a whole username, so typing the start of one showed no rows.
Any part of the name now matches, in either case. This drives the real
InputApp.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import Input

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


@pytest.mark.parametrize(
    "typed, shown",
    [
        ("first", ["first_creator"]),  # the start of a name
        ("ST_CRE", ["first_creator"]),  # the middle, any case
        (" creator ", ["first_creator", "second_creator"]),
        ("first_creator", ["first_creator"]),  # a whole name still works
        ("nobody", []),
        ("", ["first_creator", "second_creator"]),
    ],
)
def test_username_box_matches_part_of_a_name(start, typed, shown):
    async def run():
        app = table_app.InputApp()
        app.table_data = [_row(1, "first_creator"), _row(2, "second_creator")]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await _settle(pilot)
            app.query_one("#username", Input).value = typed
            app.set_filtered_rows()
            await _settle(pilot)

            assert sorted(r["username"] for r in app._filtered_rows) == shown

    asyncio.run(run())
