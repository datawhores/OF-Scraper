"""Drive column visibility, persistence and row interactions in the check app."""

import asyncio
from types import SimpleNamespace

import pytest
from textual.coordinate import Coordinate
from textual.widgets import ContentSwitcher

import ofscraper.classes.table.app as table_app
import ofscraper.utils.cache.cache as cache


EXTRA_COLUMNS = {"post_media_count", "responsetype", "price", "post_id", "media_id"}
CACHE_KEY = "check_table_show_extra_columns"


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


@pytest.fixture(autouse=True)
def fake_cache(monkeypatch):
    saved = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: saved.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value: saved.__setitem__(key, value))
    monkeypatch.setattr(
        table_app.settings, "get_settings",
        lambda: _Settings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings, "get_args",
        lambda: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    return saved


def _row(index):
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
    app.table_data = [_row(1), _row(2), _row(3)]
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
