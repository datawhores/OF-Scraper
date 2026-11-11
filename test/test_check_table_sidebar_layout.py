"""Check table sidebars: layout (#423) and the Clear Filters button (#427).

The download sidebar's size boxes each took half the sidebar and had no
label once a value was set, and the Length field's Hour/Min/Sec boxes
overlapped. These tests drive the real InputApp headless with made-up rows.
"""

import asyncio
import itertools
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import Input, Label, SelectionList

import ofscraper.classes.table.app as table_app


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _row(index, text, mediatype, length, price):
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
        "mediatype": mediatype,
        "post_date": "2024-01-01",
        "media": 1,
        "length": length,
        "responsetype": "Timeline",
        "price": price,
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": text,
    }


ROWS = [
    ("cat video", "Videos", "0:01:00", "Free"),
    ("dog picture", "Images", "N/A", 5),
    ("long cat video", "Videos", "0:20:00", 10),
]


@pytest.fixture(autouse=True)
def _stub_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings(
            db_sort="number", desc=False, size_min=10, size_max=10000
        ),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())


def _drive(steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = [_row(i + 1, *r) for i, r in enumerate(ROWS)]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(run())


async def _settle(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


@pytest.mark.parametrize(
    "field, label, value",
    [
        ("#download_size_min", "Min size (bytes)", "10"),
        ("#download_size_max", "Max size (bytes)", "10000"),
    ],
)
def test_size_fields_are_small_and_labelled(field, label, value):
    async def steps(app, pilot):
        await pilot.press("ctrl+d")
        await _settle(pilot)
        sidebar = app.query_one("#download_option_sidebar")
        node = app.query_one(field)

        assert node.region.height <= 4
        assert node.query_one(Input).value == value

        text = node.query_one(Label)
        assert str(text.render()) == label
        assert text.display and text.region.height >= 1
        assert sidebar.region.contains_region(text.region)
        # the label sits beside the box, not under it
        assert not text.region.overlaps(node.query_one(Input).region)

    _drive(steps)


def test_length_inputs_do_not_overlap():
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        field = app.query_one("#length")
        app.query_one("#options_sidebar").scroll_to_widget(
            field, animate=False, top=True
        )
        await _settle(pilot)

        inputs = list(field.query(Input))
        assert len(inputs) == 6
        for a, b in itertools.combinations(inputs, 2):
            assert not a.region.overlaps(b.region), (a.id, b.id)
        # and none is cut off by the field
        for box in inputs:
            assert field.region.contains_region(box.region), box.id

    _drive(steps)


def test_options_sidebar_fields_do_not_overlap():
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        grid = app.query_one("#main_options")
        children = list(grid.children)
        for a, b in itertools.combinations(children, 2):
            assert not a.region.overlaps(b.region), (a, b)
        for child in children:
            assert grid.region.contains_region(child.region), child

    _drive(steps)


def _selected(app, field):
    return sorted(app.query_one(field).query_one(SelectionList).selected)


def test_clear_filters_resets_every_filter_and_keeps_the_sidebar_open():
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        sidebar = app.query_one("#options_sidebar")
        button = app.query_one("#clear_filters")
        # at the top, visible without scrolling
        assert sidebar.region.contains_region(button.region)

        defaults = {
            "mediatype": _selected(app, "#mediatype"),
            "downloaded": _selected(app, "#downloaded"),
        }

        app.query_one("#text_search").value = "cat"
        app.query_one("#exact_match").value = True
        app.query_one("#min_minute").value = "5"
        app.query_one("#max_hour").value = "1"
        app.query_one("#price_min").value = "1"
        app.query_one("#price_max").value = "20"
        app.query_one("#mediatype").query_one(SelectionList).deselect("Videos")
        app.query_one("#downloaded").select_false()
        app.filter_table()
        await _settle(pilot)
        assert len(app._filtered_rows) < len(app.table_data)

        await pilot.click("#clear_filters")
        await _settle(pilot)

        for box in ["#text_search", "#price_min", "#price_max"]:
            assert app.query_one(box).value == "", box
        assert app.query_one("#exact_match").value is False
        for box in app.query_one("#length").query(Input):
            assert box.value == "", box.id
        assert _selected(app, "#mediatype") == defaults["mediatype"]
        assert _selected(app, "#downloaded") == defaults["downloaded"]

        assert len(app._filtered_rows) == len(app.table_data)
        assert app.table.row_count == len(app.table_data)
        assert app._sortkey == "number" and app._reverse is False

        assert sidebar.has_class("-show")
        assert app.focused is button

    _drive(steps)
