"""Check table download sidebar (Ctrl+D): size limits as a number and a unit.

The Min/Max size boxes took a raw byte count. They now take a whole number
and a Bytes/KB/MB/GB button (1024-based); the setting is still saved in bytes.
Every change is applied at once; only over 1 TB is refused. A min above the
max is applied with a warning. These tests drive the real InputApp headless.
"""

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Input, Static

import ofscraper.classes.table.app as table_app
from ofscraper.utils.sizes import GB, KB, MB, format_size, parse_whole_number, split_size


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


@pytest.fixture
def args(monkeypatch, tmp_path, request):
    start = getattr(request, "param", {})
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings(db_sort="number", desc=False, **start),
    )
    saved = SimpleNamespace(text=False, text_only=False, size_min=None, size_max=None)
    monkeypatch.setattr(table_app.settings, "get_args", lambda *a, **k: saved)
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())
    return saved


def _drive(steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = [_row(1)]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+d")
            await _settle(pilot)
            await steps(app, pilot)

    asyncio.run(run())


async def _settle(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


async def _set(pilot, app, field, number=None, unit=None):
    if number is not None:
        app.query_one(f"#{field}_input", Input).value = number
        await _settle(pilot)
    if unit is not None:
        await pilot.click(f"#{field}_unit_{unit}")
        await _settle(pilot)


def _hint(app, field):
    hint = app.query_one(f"#{field}").query_one(".size_hint", Static)
    return str(hint.render()), hint.has_class("-error")


def _active_unit(app, field):
    pressed = [
        b.id.rsplit("_", 1)[1]
        for b in app.query_one(f"#{field}").query(Button)
        if b.variant == "primary"
    ]
    assert len(pressed) == 1
    return int(pressed[0])


# --- the helpers ----------------------------------------------------------


@pytest.mark.parametrize(
    "size, expected",
    [(0, (0, MB)), (None, (0, MB)), (10, (10, 1)), (10 * MB, (10, MB)),
     (3 * GB, (3, GB)), (2 * KB, (2, KB)), (1536, (1536, 1)),
     (10000, (10000, 1)), ("junk", (0, MB))],
)
def test_split_size_keeps_the_saved_value_exact(size, expected):
    assert split_size(size) == expected


@pytest.mark.parametrize(
    "text, expected",
    [("", 0), ("0", 0), ("42", 42), (" 7 ", 7), ("1,024", 1024),
     ("-5", None), ("1.5", None), ("10mb", None), ("abc", None), ("٣", None)],
)
def test_parse_whole_number(text, expected):
    assert parse_whole_number(text) == expected


def test_format_size():
    assert format_size(0) == "0"
    assert format_size(10 * MB) == "10 MB"
    assert format_size(1500) == "1,500 Bytes"


# --- the sidebar ----------------------------------------------------------


def test_number_and_unit_set_the_size_in_bytes(args):
    async def steps(app, pilot):
        await _set(pilot, app, "download_size_max", "50", MB)
        assert args.size_max == 50 * MB
        # the hint doesn't repeat the size in bytes
        assert _hint(app, "download_size_max") == (
            "Whole numbers only. Empty or 0 = no limit.",
            False,
        )

        await _set(pilot, app, "download_size_max", unit=GB)
        assert args.size_max == 50 * GB
        assert _active_unit(app, "download_size_max") == GB

    _drive(steps)


def test_letters_signs_and_decimals_cannot_be_typed(args):
    async def steps(app, pilot):
        app.query_one("#download_size_min_input").focus()
        await pilot.press(*"-1a2.b3")
        await _settle(pilot)
        assert app.query_one("#download_size_min_input", Input).value == "123"

    _drive(steps)


def test_empty_or_zero_means_no_limit(args):
    async def steps(app, pilot):
        await _set(pilot, app, "download_size_min", "5", KB)
        assert args.size_min == 5 * KB
        await _set(pilot, app, "download_size_min", "")
        assert args.size_min == 0
        await _set(pilot, app, "download_size_min", "0")
        assert args.size_min == 0
        assert _hint(app, "download_size_min") == (
            "Whole numbers only. Empty or 0 = no limit.",
            False,
        )

    _drive(steps)


def test_more_than_a_terabyte_is_refused_and_not_applied(args):
    async def steps(app, pilot):
        await _set(pilot, app, "download_size_max", "2", GB)
        await _set(pilot, app, "download_size_max", "5000")
        text, error = _hint(app, "download_size_max")
        assert error and "At most 1,024 GB" in text and "Not applied" in text
        assert args.size_max == 2 * GB  # the last good value stays

    _drive(steps)


def _warning(app, field):
    hint = app.query_one(f"#{field}").query_one(".size_hint", Static)
    return hint.has_class("-warning")


def test_min_above_max_is_applied_at_once_with_a_warning(args):
    async def steps(app, pilot):
        await _set(pilot, app, "download_size_max", "10", MB)
        await _set(pilot, app, "download_size_min", "20", MB)
        # applied straight away, not held back
        assert args.size_min == 20 * MB
        text, error = _hint(app, "download_size_min")
        assert not error and _warning(app, "download_size_min")
        assert "above the max (10 MB)" in text and "Not applied" not in text

        # raising the max clears the warning
        await _set(pilot, app, "download_size_max", "30")
        assert args.size_max == 30 * MB
        assert args.size_min == 20 * MB
        assert not _warning(app, "download_size_min")
        assert _hint(app, "download_size_min")[0] == (
            "Whole numbers only. Empty or 0 = no limit."
        )

    _drive(steps)


def test_number_typed_before_its_unit_is_applied_at_each_step(args):
    """Min 2 GB, then typing a max of 10 GB: "1", "10" (MB), then GB."""

    async def steps(app, pilot):
        await _set(pilot, app, "download_size_min", "2", GB)
        await _set(pilot, app, "download_size_max", "10")
        assert args.size_max == 10 * MB
        assert _warning(app, "download_size_max")
        await _set(pilot, app, "download_size_max", unit=GB)
        assert args.size_max == 10 * GB
        assert not _warning(app, "download_size_max")
        assert not _warning(app, "download_size_min")

    _drive(steps)


@pytest.mark.parametrize(
    "args", [{"size_max": 10 * MB, "size_min": 1500}], indirect=True
)
def test_saved_sizes_open_in_their_largest_exact_unit(args):
    async def steps(app, pilot):
        assert app.query_one("#download_size_max_input", Input).value == "10"
        assert _active_unit(app, "download_size_max") == MB
        assert app.query_one("#download_size_min_input", Input).value == "1500"
        assert _active_unit(app, "download_size_min") == 1

    _drive(steps)


def test_unit_buttons_do_not_reach_the_apps_button_handler(args, monkeypatch):
    seen = []

    def handler(self, event):
        seen.append(event.button.id)

    monkeypatch.setattr(table_app.InputApp, "on_button_pressed", handler)

    async def steps(app, pilot):
        await _set(pilot, app, "download_size_max", "1", GB)
        assert seen == []

    _drive(steps)
