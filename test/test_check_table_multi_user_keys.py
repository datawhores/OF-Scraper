"""Check table with more than one creator: every row needs its own key.

row_gather numbered each creator's rows from 1 and used that as "index",
the table's row key, so the second creator's first row hit Textual's
DuplicateKey ("The row key '1' already exists") and the table crashed.
"index" now continues across creators; "number" still counts per creator.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest

import ofscraper.classes.table.app as table_app
import ofscraper.commands.check as check


class _Log:
    def info(self, *a, **k):
        pass

    warning = debug = info


def _media(media_id, post_id, date):
    post = SimpleNamespace(post_media=[1], price=0)
    return SimpleNamespace(
        id=media_id,
        post_id=post_id,
        date=date,
        postdate=date,
        formatted_postdate=date,
        canview=True,
        mpd=None,
        url="https://example.invalid/x.jpg",
        _post=post,
        post=SimpleNamespace(db_sanitized_text="t"),
        mediatype="images",
        numeric_duration="N/A",
        responsetype="timeline",
    )


def _collection(count, base):
    media = [
        _media(base + i, base + i, f"2024-01-{i + 1:02d} 00:00:00")
        for i in range(count)
    ]
    return SimpleNamespace(all_media=media, posts_with_media_id=lambda _id: [])


@pytest.fixture
def rows(monkeypatch):
    monkeypatch.setattr(check, "log", _Log())
    monkeypatch.setattr(check, "get_media_post_files_downloaded", lambda **kw: {})
    monkeypatch.setattr(
        check,
        "check_user_dict",
        {"1": {"collection": _collection(3, 100)}, "2": {"collection": _collection(2, 200)}},
    )
    monkeypatch.setattr(check, "ROWS", [])

    async def gather():
        await check.row_gather("first", 1)
        await check.row_gather("second", 2)

    asyncio.run(gather())
    return check.ROWS


def test_index_is_unique_across_creators(rows):
    assert [r["index"] for r in rows] == [1, 2, 3, 4, 5]
    # the Number column still counts within each creator
    assert [(r["username"], r["number"]) for r in rows] == [
        ("first", 1),
        ("first", 2),
        ("first", 3),
        ("second", 1),
        ("second", 2),
    ]


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def test_table_opens_with_two_creators(rows, monkeypatch, tmp_path):
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

    async def run():
        app = table_app.InputApp()
        app.table_data = rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            # sorted by number, the two creators' rows interleave
            assert app.table.row_count == 5

    asyncio.run(run())
