"""Check table filter sidebar (Ctrl+S): which Length box is hours, minutes, seconds.

The Min/Max length boxes name their unit only as placeholder text, which a
value hides, and a saved or picked length filled all three with "0", zeros
included, so no box said which it was. A zero part is now left empty, so its
placeholder (Hours/Minutes/Seconds) shows. These tests drive the real
InputApp.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import Input, Label

import ofscraper.classes.table.app as table_app


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _row(index, length):
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
        "length": length,
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": "t",
    }


@pytest.fixture
def start(monkeypatch, tmp_path, request):
    values = getattr(request, "param", {})
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings(db_sort="number", desc=False, **values),
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
        app.table_data = [_row(1, "0:01:30")]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await _settle(pilot)
            field = app.query_one("#length")
            app.query_one("#options_sidebar").scroll_to_widget(
                field, animate=False, top=True
            )
            await _settle(pilot)
            await steps(app, pilot, field)

    asyncio.run(run())


def _values(app, *ids):
    return [app.query_one(f"#{i}", Input).value for i in ids]


MIN = ("min_hour", "min_minute", "min_second")
MAX = ("max_hour", "max_minute", "max_second")


def test_each_box_names_its_unit(start):
    async def steps(app, pilot, field):
        for row in (MIN, MAX):
            assert [app.query_one(f"#{b}", Input).placeholder for b in row] == [
                "Hours",
                "Minutes",
                "Seconds",
            ]

    _drive(steps)


def test_rows_are_labelled(start):
    async def steps(app, pilot, field):
        for container, text in [("#minContainer", "Min length"), ("#maxContainer", "Max length")]:
            label = field.query_one(container).query_one(Label)
            assert str(label.render()) == text

    _drive(steps)


def test_row_labels_line_up_with_their_boxes(start):
    async def steps(app, pilot, field):
        for container, box in [("#minContainer", "#min_hour"), ("#maxContainer", "#max_hour")]:
            label = field.query_one(container).query_one(Label)
            box = app.query_one(box, Input)
            # the label is as tall as the box and its text sits on the middle
            # line, where the box's own text is
            assert (label.region.y, label.region.height) == (box.region.y, box.region.height)
            assert label.styles.content_align_vertical == "middle"

    _drive(steps)


@pytest.mark.parametrize(
    "start", [{"length_min": 90, "length_max": 3600}], indirect=True
)
def test_saved_lengths_leave_zero_parts_empty(start):
    async def steps(app, pilot, field):
        assert _values(app, *MIN) == ["", "1", "30"]
        assert _values(app, *MAX) == ["1", "", ""]
        # an empty part is the placeholder, still telling you which box it is
        assert app.query_one("#max_minute", Input).placeholder == "Minutes"

    _drive(steps)


def test_a_picked_length_leaves_zero_parts_empty(start):
    async def steps(app, pilot, field):
        field.update_table_val("0:01:30")
        await _settle(pilot)
        assert _values(app, *MIN) == ["", "1", "30"]
        assert _values(app, *MAX) == ["", "1", "30"]
        # and the filter still matches that length
        assert field.compare("0:01:30")
        assert not field.compare("0:02:00")

    _drive(steps)
