"""Check-table clicks, shortcuts, column visibility, colors, logging, and multi-user keys."""

# ----------------------------------------------------------------------
# From test_check_table_copy_username.py
# Check table: a right-click copies a username or the other posts' ids.
#
# The table is drawn by the app, so the terminal can't select text from it.
# A right-click on a cell in the UserName or Other_Posts_With_Media column
# copies it to the clipboard and says so. It doesn't select the cell, and a
# right-click on any other column is unchanged. These tests drive the real
# InputApp.
# ----------------------------------------------------------------------

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.coordinate import Coordinate

import ofscraper.classes.table.app as table_app


class _Settings_copy(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _row_copy(index, username):
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
        lambda *a, **k: _Settings_copy(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())


async def _settle_copy(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


def _drive_copy(steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = [_row_copy(1, "first_creator"), _row_copy(2, "second_creator")]
        app.table_data[0]["other_posts_with_media"] = [111, 222]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await _settle_copy(pilot)
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
    await _settle_copy(pilot)


def test_right_click_copies_the_username(start):
    async def steps(app, pilot, table, notices):
        before = table.cursor_coordinate

        await _click(pilot, table, 1, "username", button=3)

        assert app.clipboard == "second_creator"
        assert notices == ["Copied second_creator"]
        # the cell isn't selected, so the cursor stays where it was
        assert table.cursor_coordinate == before

    _drive_copy(steps)


def test_right_click_copies_other_posts_with_media(start):
    async def steps(app, pilot, table, notices):
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

    _drive_copy(steps)


def test_right_click_elsewhere_copies_nothing(start):
    async def steps(app, pilot, table, notices):
        await _click(pilot, table, 1, "mediatype", button=3)

        assert app.clipboard == ""
        assert notices == []

    _drive_copy(steps)


def test_left_click_on_a_username_copies_nothing(start):
    async def steps(app, pilot, table, notices):
        await _click(pilot, table, 1, "username", button=1)

        assert app.clipboard == ""
        assert notices == []
        assert table.cursor_coordinate.row == 1

    _drive_copy(steps)

# ----------------------------------------------------------------------
# From test_check_table_enter_on_number.py
# Check table: Enter on the Number cell works like Enter on the Download cell.
#
# On the main table it adds the row to the cart (or takes it out again); on
# the cart table it removes the row. These tests drive the real InputApp
# headless with made-up rows.
# ----------------------------------------------------------------------

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.coordinate import Coordinate

import ofscraper.classes.table.app as table_app


class _Settings_enter(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _row_enter(index, unlocked=True):
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


@pytest.fixture
def _stub_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings_enter(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())


def _drive_enter(rows, steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(run())


async def _settle_enter(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


def _cart(app):
    return [r["index"] for r in app.table_data if r["download_cart"] == "[added]"]


async def _enter_on(pilot, table, row, column):
    table.focus()
    table.cursor_coordinate = Coordinate(row, table.ordered_columns_keys.index(column))
    await _settle_enter(pilot)
    await pilot.press("enter")
    await _settle_enter(pilot)


def _cell(table, row, column):
    value = table.get_cell_at(Coordinate(row, table.ordered_columns_keys.index(column)))
    return getattr(value, "plain", value)


@pytest.mark.usefixtures("_stub_settings")
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

    _drive_enter([_row_enter(1), _row_enter(2), _row_enter(3)], steps)


@pytest.mark.usefixtures("_stub_settings")
def test_enter_on_number_skips_locked_media_like_the_download_cell():
    async def steps(app, pilot):
        await _enter_on(pilot, app.table, 0, "number")
        assert _cart(app) == []

    _drive_enter([_row_enter(1, unlocked=False)], steps)


@pytest.mark.usefixtures("_stub_settings")
@pytest.mark.parametrize("column", ["number", "download_cart"])
def test_enter_on_the_cart_table_removes_the_row(column):
    async def steps(app, pilot):
        await pilot.press("a")  # add the page
        await _settle_enter(pilot)
        assert _cart(app) == [1, 2]
        await pilot.click("#cart")
        await _settle_enter(pilot)
        cart_table = app.query_one("#cart_data_table")
        assert cart_table.row_count == 2

        await _enter_on(pilot, cart_table, 0, column)

        assert len(_cart(app)) == 1
        assert cart_table.row_count == 1

    _drive_enter([_row_enter(1), _row_enter(2)], steps)


@pytest.mark.usefixtures("_stub_settings")
def test_enter_on_another_column_does_not_change_the_cart():
    async def steps(app, pilot):
        await _enter_on(pilot, app.table, 0, "username")
        assert _cart(app) == []

    _drive_enter([_row_enter(1)], steps)

# ----------------------------------------------------------------------
# From test_check_table_hide_columns.py
# Drive column visibility, persistence and row interactions in the check app.
# ----------------------------------------------------------------------

import asyncio
from types import SimpleNamespace

import pytest
from textual.coordinate import Coordinate
from textual.widgets import ContentSwitcher

import ofscraper.classes.table.app as table_app
import ofscraper.utils.cache.cache as cache


EXTRA_COLUMNS = {"post_media_count", "responsetype", "price", "post_id", "media_id"}
CACHE_KEY = "check_table_show_extra_columns"


class _Settings_hide(SimpleNamespace):
    def __getattr__(self, name):
        return None


@pytest.fixture
def fake_cache(monkeypatch):
    saved = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: saved.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value: saved.__setitem__(key, value))
    monkeypatch.setattr(
        table_app.settings, "get_settings",
        lambda: _Settings_hide(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings, "get_args",
        lambda: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    return saved


def _row_hide(index):
    return dict(
        index=index, number=index, download_cart="[]", username="",
        downloaded=False, unlocked=True, download_type="normal",
        other_posts_with_media=[], length="0:01:00", mediatype="Videos",
        post_date="2024-01-01", post_media_count=index, responsetype="Timeline",
        price="Free", post_id=100 + index, media_id=1000 + index,
        text=f"row {index}",
    )


def _app():
    app = table_app.InputApp()
    app.table_data = [_row_hide(1), _row_hide(2), _row_hide(3)]
    app._sortkey = None
    app._reverse = False
    return app


def _assert_columns(app, shown):
    for table in (app.table, app.query_one("#cart_data_table")):
        columns = set(table.ordered_columns_keys)
        assert columns & EXTRA_COLUMNS == (EXTRA_COLUMNS if shown else set())
        assert {"download_cart", "downloaded", "text"} <= columns


async def _click_cart_cell(pilot, table, row_index):
    # Textual selects on a click of the highlighted cell; a click elsewhere
    # only moves the cursor. Highlight first, then exercise the real mouse event.
    column = table.ordered_columns_keys.index("download_cart")
    coordinate = Coordinate(row_index, column)
    table.move_cursor(row=row_index, column=column)
    await pilot.pause()
    assert table.cursor_coordinate == coordinate
    region = table._get_cell_region(coordinate)
    assert await pilot.click(table, offset=(region.x + 1, region.y))
    await pilot.pause()


def test_columns_hidden_by_default_and_h_toggles_both_tables(fake_cache):
    async def drive():
        app = _app()
        app.table_data[1]["download_cart"] = "[added]"
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            _assert_columns(app, False)
            await pilot.press("h")
            _assert_columns(app, True)
            assert fake_cache == {CACHE_KEY: True}
            cart = app.query_one("#cart_data_table")
            assert cart.get_cell("2", "media_id").plain == "1002"
            assert app.table.get_cell("3", "text").plain == "row 3"
            # Toggle from the cart too, with its rows visible.
            await pilot.click("#cart")
            await pilot.press("h")
            _assert_columns(app, False)
            assert fake_cache == {CACHE_KEY: False}
            assert cart.get_cell("2", "text").plain == "row 2"

    asyncio.run(drive())


@pytest.mark.usefixtures("fake_cache")
def test_hidden_media_id_filter_keeps_working_after_toggles():
    async def drive():
        app = _app()
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            _assert_columns(app, False)
            await pilot.press("ctrl+s")
            app.query_one("#media_id_input").value = "1002"
            await pilot.click("#filter")
            await pilot.pause()
            assert [row["index"] for row in app._filtered_rows] == [2]
            for shown in (True, False):
                assert app.table.row_count == 1
                assert app.table.get_cell("2", "text").plain == "row 2"
                await pilot.press("h")
                _assert_columns(app, shown)
            assert app.table.row_count == 1

    asyncio.run(drive())


@pytest.mark.parametrize("shown", [False, True])
def test_cart_cell_clicks_and_download_updates_use_row_and_column_keys(shown, fake_cache):
    fake_cache[CACHE_KEY] = shown

    async def drive():
        app = _app()
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            _assert_columns(app, shown)
            await _click_cart_cell(pilot, app.table, 1)
            assert [r["index"] for r in app.table_data if r["download_cart"] == "[added]"] == [2]
            assert app.table.get_cell("2", "download_cart").plain == "[added]"
            await pilot.click("#cart")
            cart = app.query_one("#cart_data_table")
            assert cart.get_cell("2", "text").plain == "row 2"
            await _click_cart_cell(pilot, cart, 0)
            assert cart.row_count == 0
            assert app.table_data[1]["download_cart"] == "[]"
            assert app.table.get_cell("2", "download_cart").plain == "[]"
            app.update_cell_state("3", "[downloaded]", "bold green")
            assert app.table.get_cell("3", "download_cart").plain == "[downloaded]"
            assert app.table.get_cell("3", "downloaded").plain == "True"
            assert app.table.get_cell("2", "downloaded").plain == "False"

    asyncio.run(drive())


def test_saved_visibility_is_loaded_on_each_open_and_toggles_are_saved(fake_cache):
    fake_cache[CACHE_KEY] = True

    async def drive():
        for shown in (True, False, True):
            app = _app()
            async with app.run_test(size=(240, 60)) as pilot:
                await pilot.pause()
                _assert_columns(app, shown)
                await pilot.press("h")
                _assert_columns(app, not shown)
                assert fake_cache == {CACHE_KEY: not shown}

    asyncio.run(drive())


@pytest.mark.usefixtures("fake_cache")
@pytest.mark.parametrize("disabled", [False, True])
def test_unavailable_or_disabled_cache_defaults_to_hidden(monkeypatch, disabled):
    def unavailable(*args, **kwargs):
        raise OSError("cache unavailable")

    monkeypatch.setattr(cache, "get", (lambda key, default=None: default) if disabled else unavailable)
    monkeypatch.setattr(cache, "set", (lambda *args: None) if disabled else unavailable)

    async def drive():
        app = _app()
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            _assert_columns(app, False)
            await pilot.press("h")
            _assert_columns(app, True)
            await pilot.press("h")
            _assert_columns(app, False)

    asyncio.run(drive())


@pytest.mark.parametrize("shown", [False, True])
def test_paging_header_sorting_and_cell_filter_shortcut(shown, fake_cache):
    fake_cache[CACHE_KEY] = shown

    async def drive():
        app = _app()
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            _assert_columns(app, shown)
            app.query_one("#main_per_page_input").value = "1"
            app.handle_pagination("main", "main_next")
            assert app.main_page == 2
            assert app.table.get_cell("2", "text").plain == "row 2"
            # Sorting via the real header event while preserving the page.
            # clear()/add_row() defer row-label sizing until the next layout.
            # Before that, x=0 points at the corner rather than Number's header.
            await pilot.pause()
            region = app.table._get_cell_region(Coordinate(0, 0))
            assert await pilot.click(app.table, offset=(region.x + 1, 0))
            await pilot.pause()
            assert app._sortkey == "number"
            assert app._reverse is True
            assert [r["index"] for r in app._filtered_rows] == [3, 2, 1]
            await pilot.press("h")
            assert app.main_page == 2
            assert app.table.get_cell("2", "text").plain == "row 2"
            # Text follows the omitted columns: copying it must use its visible index.
            column = app.table.ordered_columns_keys.index("text")
            app.table.move_cursor(row=0, column=column)
            app.table.focus()
            await pilot.pause()
            assert app.table.cursor_coordinate == Coordinate(0, column)
            await pilot.press(";")
            await pilot.pause()
            assert app.query_one("#text_search").value == "row 2"
            app.query_one("#text").reset()
            await pilot.press("A")
            await pilot.click("#cart")
            assert app.query_one(ContentSwitcher).current == "cart_page"
            app.query_one("#cart_per_page_input").value = "1"
            app.handle_pagination("cart", "cart_next")
            assert app.cart_page == 2
            cart = app.query_one("#cart_data_table")
            assert cart.get_cell("2", "text").plain == "row 2"
            await pilot.press("h")
            assert app.cart_page == 2
            assert cart.get_cell("2", "text").plain == "row 2"

    asyncio.run(drive())

# ----------------------------------------------------------------------
# From test_check_table_colors.py
# Check table: the header labels use the terminal's palette colours.
#
# Since textual 2, Static parses Textual markup, where blue, green, red, yellow
# and cyan are fixed truecolours (#0000ff, ...), not the terminal's ANSI colours
# that Rich markup gave on textual 1.0. Bold-blue labels came out dark blue on
# the near-black background, and with NO_COLOR they turned the background's
# colour and disappeared. The ansi_* names give the ANSI colours back.
# ----------------------------------------------------------------------

import asyncio
from types import SimpleNamespace

from textual.style import Style

import ofscraper.classes.table.app as table_app

# ANSI colour numbers
RED, GREEN, YELLOW, BLUE, CYAN = 1, 2, 3, 4, 6


class _Settings_colors(SimpleNamespace):
    def __getattr__(self, name):
        return None


def test_header_labels_use_palette_colours(monkeypatch):
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings_colors(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)

    async def drive():
        app = table_app.InputApp()
        app.table_data = []  # also shows "All Items Filtered Out"
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            # the headers of the table, cart and console pages, after the
            # info and toggle labels have been filled in
            found = []
            for widget in app.query(".header_top_row Static"):
                content = widget.visual
                for span in getattr(content, "spans", []):
                    style = span.style
                    if isinstance(style, str):
                        style = Style.parse(style)
                    if style.foreground is not None:
                        label = str(content)[span.start : span.end]
                        found.append((label, style.foreground.ansi))
            return found

    found = asyncio.run(drive())
    assert [label for label, ansi in found if ansi is None] == []
    assert {ansi for _, ansi in found} == {RED, GREEN, YELLOW, BLUE, CYAN}

# ----------------------------------------------------------------------
# From test_check_table_console_log.py
# Check table: logging after the table has closed doesn't raise.
#
# The table's console page shows the "shared" log through a TextHandler. Once
# the console page had been on screen (Send Downloads switches to it), the
# handler kept writing to it after the app exited, and RichLog.write raised
# NoActiveAppError: the "Finished Script" message at exit crashed the run,
# and a download still running in the worker thread would have stopped at its
# next log line.
# ----------------------------------------------------------------------

import asyncio
import logging
import queue
import threading
from types import SimpleNamespace

import ofscraper.classes.table.app as table_app
from ofscraper.utils.logs.classes.handlers.text import TextHandler


class _Settings_conlog(SimpleNamespace):
    def __getattr__(self, name):
        return None


def test_logging_after_the_table_closes(monkeypatch):
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings_conlog(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())

    shared = logging.getLogger("shared")
    handler = TextHandler()
    old_level = shared.level
    shared.addHandler(handler)
    shared.setLevel(logging.DEBUG)
    try:

        async def drive():
            app = table_app.InputApp()
            app.table_data = []
            app._sortkey = None
            app._reverse = False
            async with app.run_test(size=(240, 60)) as pilot:
                await pilot.pause()
                console_log = app.query_one("#console_page_log")
                assert handler.widget is console_log
                # Send Downloads with an empty cart shows the console page
                app.query_one("#send_downloads_main").press()
                await pilot.pause()
                shared.info("while the table is open")
                await pilot.pause()
                assert console_log.lines  # written, not just queued
            return console_log

        asyncio.run(drive())
        # after the app has exited: the message at exit, and one from a
        # download still running in the worker thread
        shared.info("Finished Script")
        errors = []

        def worker():
            try:
                shared.info("download finished")
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(5)
        assert errors == []
        assert handler.widget is None
    finally:
        shared.removeHandler(handler)
        shared.setLevel(old_level)


def _record(message):
    return logging.LogRecord("shared", logging.INFO, __file__, 1, message, None, None)


def test_the_handler_skips_a_widget_that_is_not_in_an_app():
    written = []
    handler = TextHandler()
    handler.widget = SimpleNamespace(is_attached=False, write=written.append)
    handler.handle(_record("not shown"))
    assert written == []


def test_the_handler_doesnt_raise_when_the_write_fails(monkeypatch):
    def write(text):
        raise RuntimeError("the app went away")

    handled = []
    handler = TextHandler()
    handler.widget = SimpleNamespace(is_attached=True, write=write)
    monkeypatch.setattr(handler, "handleError", handled.append)
    handler.handle(_record("lost"))
    assert [r.getMessage() for r in handled] == ["lost"]

# ----------------------------------------------------------------------
# From test_check_table_multi_user_keys.py
# Check table with more than one creator: every row needs its own key.
#
# row_gather numbered each creator's rows from 1 and used that as "index",
# the table's row key, so the second creator's first row hit Textual's
# DuplicateKey ("The row key '1' already exists") and the table crashed.
# "index" now continues across creators; "number" still counts per creator.
# ----------------------------------------------------------------------

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


class _Settings_multi(SimpleNamespace):
    def __getattr__(self, name):
        return None


def test_table_opens_with_two_creators(rows, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings_multi(db_sort="number", desc=False),
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
            assert app.table.row_count == 5

    asyncio.run(run())


def test_sorting_by_number_keeps_each_creator_together(rows):
    # "number" restarts for each creator, so sorting on it alone gave
    # first 1, second 1, first 2, second 2, first 3
    app = table_app.InputApp()
    app.table_data = list(reversed(rows))

    app._reverse = False
    app._sort_runner("number")
    assert [(r["username"], r["number"]) for r in app.table_data] == [
        ("first", 1),
        ("first", 2),
        ("first", 3),
        ("second", 1),
        ("second", 2),
    ]

    app._reverse = True
    app._sort_runner("number")
    assert [(r["username"], r["number"]) for r in app.table_data] == [
        ("second", 2),
        ("second", 1),
        ("first", 3),
        ("first", 2),
        ("first", 1),
    ]


# ----------------------------------------------------------------------
# Check table: long values stay on one line; Per Page redraws once,
# never divides by 0, and is skipped after the app closes; Length sorts
# day-long and fractional lengths.
# ----------------------------------------------------------------------

import asyncio
import queue
from types import SimpleNamespace

import pytest

import ofscraper.classes.table.app as table_app
import ofscraper.classes.table.utils.post_metrics as post_metrics


class _Settings_hf(SimpleNamespace):
    def __getattr__(self, name):
        return None


@pytest.fixture
def stub_env_hf(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings_hf(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )


def _media_row_hf(index, **values):
    row = {
        "index": index,
        "number": index,
        "download_cart": "[]",
        "username": "creator_a",
        "downloaded": False,
        "unlocked": True,
        "download_type": "normal",
        "other_posts_with_media": [],
        "post_media_count": 1,
        "mediatype": "Videos",
        "post_date": "2024-05-01 12:00:00",
        "length": "0:01:00",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": "post",
    }
    row.update(values)
    return row


def _media_obj_hf(mid, pid, mtype="images", canview=True):
    return SimpleNamespace(
        id=mid,
        post_id=pid,
        mediatype=mtype,
        numeric_duration=None,
        duration=None,
        canview=canview,
    )


def _post_obj_hf(pid, price, items, date="2024-05-01 12:00:00"):
    return SimpleNamespace(
        id=pid,
        price=price,
        opened=1,
        all_media=items,
        responsetype="timeline",
        formatted_date=date,
        db_sanitized_text="post",
    )


def _app_hf(media_rows, post_rows):
    app = table_app.InputApp()
    app.table_data = media_rows
    app.post_data = post_rows
    app._sortkey = None
    app._reverse = False
    return app


LONG_ID_hf = 123456789012345678


LONG_NAME_hf = "a_long_creator_x"  # 16 characters


def test_long_values_stay_on_one_line(stub_env_hf):
    # columns narrower than the old 18 (media) and 16 (posts) wrapped these
    # values onto a second line, doubling the row height
    media_rows = [
        _media_row_hf(
            1,
            post_id=LONG_ID_hf,
            media_id=LONG_ID_hf,
            post_date="2024-05-01",
            username=LONG_NAME_hf,
        ),
        _media_row_hf(2, post_date="Probably Deleted"),
    ]
    post_rows = post_metrics.build_post_centric_rows(
        [_post_obj_hf(2, 0, [_media_obj_hf(2, 2)])], LONG_NAME_hf, 1
    )

    async def drive():
        app = _app_hf(media_rows, post_rows)
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            await pilot.press("h")  # show the id columns
            await pilot.pause()
            assert {"post_id", "media_id"} <= set(app.table.ordered_columns_keys)
            assert [r.height for r in app.table.rows.values()] == [1, 1]

            await pilot.click("#post_tab")
            await pilot.pause()
            assert "username" in app.post_table.ordered_columns_keys
            assert [r.height for r in app.post_table.rows.values()] == [1]

    asyncio.run(drive())


def test_two_other_post_ids_stay_on_one_line(stub_env_hf):
    # "[1234567890, 1234567891]" is 24 characters
    media_rows = [
        _media_row_hf(
            1, post_date="2024-05-01", other_posts_with_media=[1234567890, 1234567891]
        )
    ]

    async def drive():
        app = _app_hf(media_rows, [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            assert "other_posts_with_media" in app.table.ordered_columns_keys
            assert [r.height for r in app.table.rows.values()] == [1]

    asyncio.run(drive())


def test_long_and_fractional_lengths_sort_by_their_real_length():
    lengths = ["2 days, 0:00:00", "2:00:00", "0:01:30.500000", "1 day, 1:00:00", "0:01:00"]
    app = table_app.InputApp()
    app.table_data = [_media_row_hf(n, length=v) for n, v in enumerate(lengths, 1)]
    app._reverse = False

    app._sort_runner("length")

    assert [r["length"] for r in app.table_data] == [
        "0:01:00",
        "0:01:30.500000",
        "2:00:00",
        "1 day, 1:00:00",
        "2 days, 0:00:00",
    ]


def _count_page_builds_hf(monkeypatch):
    counts = {"main": 0, "post": 0, "cart": 0}
    for prefix, name in (
        ("main", "set_page"),
        ("post", "set_post_page"),
        ("cart", "update_cart_table"),
    ):
        original = getattr(table_app.InputApp, name)

        def counted(self, *a, _orig=original, _prefix=prefix, **k):
            counts[_prefix] += 1
            return _orig(self, *a, **k)

        monkeypatch.setattr(table_app.InputApp, name, counted)
    return counts


def test_per_page_builds_each_table_once_at_startup(stub_env_hf, monkeypatch):
    counts = _count_page_builds_hf(monkeypatch)

    async def drive():
        app = _app_hf([_media_row_hf(n) for n in range(1, 4)], [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause(0.6)
            assert counts["main"] == 1
            assert counts["post"] == 1
            assert counts["cart"] <= 1

    asyncio.run(drive())


def test_typing_a_per_page_value_builds_the_table_once(stub_env_hf, monkeypatch):
    counts = _count_page_builds_hf(monkeypatch)
    # long enough that a busy machine can't fire it between two keystrokes
    monkeypatch.setattr(table_app.InputApp, "PER_PAGE_DELAY", 1.0)

    async def drive():
        app = _app_hf([_media_row_hf(n) for n in range(1, 4)], [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause(0.6)
            box = app.query_one("#main_per_page_input")
            box.focus()
            box.value = ""
            await pilot.pause()
            counts["main"] = 0
            await pilot.press("5", "0", "0", "0")
            await pilot.pause(1.5)
            assert counts["main"] == 1
            assert app.table.row_count == 3

    asyncio.run(drive())


def test_a_per_page_of_zero_draws_the_default_page_size(stub_env_hf):
    # 0 stays in the box (it isn't above 0, so typing it redraws nothing);
    # the next filter, sort or cart redraw divided by it
    media_rows = [_media_row_hf(n, post_date="2024-05-01") for n in range(1, 4)]
    media_rows[0]["download_cart"] = "[added]"
    post_rows = post_metrics.build_post_centric_rows(
        [_post_obj_hf(n, 0, [_media_obj_hf(n, n)]) for n in range(1, 4)], "creator_a", 1
    )

    async def drive():
        app = _app_hf(media_rows, post_rows)
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            for prefix in ("main", "post", "cart"):
                app.query_one(f"#{prefix}_per_page_input").value = "0"
            await pilot.pause(0.5)
            app.filter_table()
            app.filter_post_table()
            app.update_cart_table()
            await pilot.pause()
            assert app.table.row_count == 3
            assert app.post_table.row_count == 3
            assert app.query_one("#cart_data_table").row_count == 1

    asyncio.run(drive())


def test_a_per_page_redraw_after_the_app_closed_does_nothing(stub_env_hf):
    # the 0.3 s wait can end while the app is closing and its inputs are gone
    async def drive():
        app = _app_hf([_media_row_hf(1)], [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
        for prefix in ("main", "post", "cart"):
            app._apply_per_page(prefix)

    asyncio.run(drive())
