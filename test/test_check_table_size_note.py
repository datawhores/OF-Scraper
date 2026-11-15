"""Check table download sidebar (Ctrl+D): say when the size limits apply.

A scan doesn't know file sizes (the download request reports them), so
setting a min or max changes nothing in the table, and that looked like
the limits weren't working. A note under the boxes says they apply when
files download.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import Static

import ofscraper.classes.table.app as table_app


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


@pytest.fixture(autouse=True)
def _stub(monkeypatch, tmp_path):
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


def _row():
    return {
        "index": 1, "number": 1, "download_cart": "[]", "username": "a_creator",
        "downloaded": False, "unlocked": True, "download_type": "normal",
        "other_posts_with_media": [], "post_media_count": 1, "mediatype": "Videos",
        "post_date": "2024-01-01", "media": 1, "length": "0:01:00",
        "responsetype": "Timeline", "price": "Free", "post_id": 101,
        "media_id": 1001, "text": "t",
    }


@pytest.mark.parametrize("width", [245, 120])
def test_note_says_when_the_limits_apply(width):
    async def run():
        app = table_app.InputApp()
        app.table_data = [_row()]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(width, 60)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+d")
            for _ in range(5):
                await pilot.pause(0.02)

            sidebar = app.query_one("#download_option_sidebar")
            note = app.query_one("#size_limit_note", Static)
            text = " ".join(str(note.render()).split())
            assert "apply when files download" in text
            assert "a scan doesn't know file sizes" in text
            assert "[skipped]" not in text

            # shown in full under both boxes, inside the sidebar
            assert note.display and note.region.height >= 2
            assert sidebar.region.contains_region(note.region)
            box = app.query_one("#download_size_max").region
            assert note.region.y >= box.bottom

    asyncio.run(run())
