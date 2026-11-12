"""Check table: an item skipped from the table isn't marked downloaded (#353).

Since #326 the database doesn't record a size-limit or script skip as
downloaded, so the table's Downloaded column, its stats and its filter don't
either, and a skipped row can be added to the cart again like a failed one.
The Downloaded cell is redrawn along with the download cell (#358).
These tests send rows through the real process_download_queue and
InputApp.update_cell_state with the download faked.
"""

import asyncio
import queue
import threading
import time
from types import SimpleNamespace

import pytest
from textual.widgets import ContentSwitcher

import ofscraper.classes.table.app as table_app
import ofscraper.commands.check as check

# process_dicts returns (videos, audios, photos, forced_skipped, skipped);
# forced_skipped is a size-limit or script skip, skipped is a failure
DOWNLOADED = (0, 0, 1, 0, 0)
SIZE_SKIPPED = (0, 0, 0, 1, 0)
FAILED = (0, 0, 0, 0, 1)


class _StopLoop(BaseException):
    """Ends process_download_queue's endless loop; not caught by its handlers."""


class _Cell:
    def __init__(self):
        self.text = None

    def update(self, text):
        self.text = text


class _FakeTable:
    def __init__(self):
        self.cells = {}

    def update_cell_at_key(self, key, col, value):
        self.cells[(key, col)] = value


class _FakeApp:
    """Borrows InputApp's real methods, with no Textual screen behind them."""

    update_cell_state = table_app.InputApp.update_cell_state
    update_search_info = table_app.InputApp.update_search_info
    _filter_runner = table_app.InputApp._filter_runner
    action_select_all_undownloaded = table_app.InputApp.action_select_all_undownloaded
    action_select_page_undownloaded = (
        table_app.InputApp.action_select_page_undownloaded
    )
    action_select_current_page = table_app.InputApp.action_select_current_page
    action_select_all_filtered = table_app.InputApp.action_select_all_filtered
    action_select_unique_all_filtered = (
        table_app.InputApp.action_select_unique_all_filtered
    )
    _add_items_to_cart = table_app.InputApp._add_items_to_cart
    _run_unique_selection = table_app.InputApp._run_unique_selection
    on_data_table_cell_selected = table_app.InputApp.on_data_table_cell_selected
    add_to_row_queue = table_app.InputApp.add_to_row_queue

    def __init__(self, rows):
        self.table_data = rows
        self._filtered_rows = list(rows)
        self.table = _FakeTable()
        self._sortkey = "number"
        self._reverse = False
        self.main_page = 1
        self.is_sidebar_open = False
        self.nodes = {
            "#main_per_page_input": SimpleNamespace(value=50),
            "#db_info_bar": _Cell(),
            "#view_info_bar": _Cell(),
        }

    def query_one(self, selector):
        if selector is ContentSwitcher:
            return SimpleNamespace(current="table_page")
        return self.nodes[selector]

    def update_cart_info(self):
        pass

    def set_page(self):
        pass


def _row(index, media_id):
    return {
        "index": index,
        "number": index + 1,
        "media_id": media_id,
        "post_id": 100 + media_id,
        "username": "a_creator",
        "unlocked": True,
        "downloaded": False,
        "download_type": "normal",
        "download_cart": "[downloading]",
        "mediatype": "images",
    }


def _fake_download(monkeypatch, rows, results):
    """Fake everything around process_download_queue except the queue and
    sleep: each media id's download returns the result given for it. Returns
    a list that gets an entry when the batch has finished."""
    media = {
        row["media_id"]: SimpleNamespace(
            id=row["media_id"],
            filename=f"file{row['media_id']}.jpg",
            post=SimpleNamespace(id=row["post_id"]),
        )
        for row in rows
    }
    collection = SimpleNamespace(find_media_item=lambda mid: media.get(mid))
    monkeypatch.setitem(check.check_user_dict, "1", {"collection": collection})

    def fake_get_data(row):
        item = media[int(row["media_id"])]
        return item, item.post, row["username"], 1

    def fake_process_dicts(username, model_id, medialist, posts, on_result=None):
        totals = [0] * 5
        for media in medialist:
            values = results[media.id]
            totals = [a + b for a, b in zip(totals, values)]
            if on_result is not None:
                result = (
                    "failed" if values[-1] else
                    "skipped" if values[-2] else "downloaded"
                )
                on_result(media, result)
        return tuple(totals)

    done = []
    model_manager = SimpleNamespace(
        get_model=lambda username: SimpleNamespace(
            id=1, active=True, expired_string=None
        ),
        mark_as_processed=lambda *a, **k: None,
        clear_scrape_queues=lambda: None,
    )
    stats_manager = SimpleNamespace(
        update_and_print_stats=lambda *a, **k: None,
        clear_scraper_activity_stats=lambda: None,
    )
    monkeypatch.setattr(
        check.manager,
        "Manager",
        SimpleNamespace(
            current_model_manager=model_manager, stats_manager=stats_manager
        ),
    )
    monkeypatch.setattr(check, "_get_data_from_row", fake_get_data)
    monkeypatch.setattr(check, "process_dicts", fake_process_dicts)
    monkeypatch.setattr(check, "data_refill", lambda model_id: None)
    monkeypatch.setattr(check, "after_download_action_script", lambda *a: None)
    monkeypatch.setattr(check, "final_action", lambda: done.append(True))
    monkeypatch.setattr(check.operations, "table_init_create", lambda **k: None)
    monkeypatch.setattr(check.network, "check_cdm", lambda: True)
    return done


@pytest.fixture
def run_queue(monkeypatch):
    """Send rows through process_download_queue; each media id's download
    returns the result given for it."""

    def run(rows, results):
        app = _FakeApp(rows)
        row_queue = queue.Queue()
        for row in rows:
            row_queue.put((str(row["index"]), row))
        monkeypatch.setattr(table_app, "row_queue", row_queue)
        monkeypatch.setattr(table_app, "app", app, raising=False)
        done = _fake_download(monkeypatch, rows, results)

        def fake_sleep(seconds):
            # The retry after a failure sleeps too; stop only once the batch
            # has finished
            if done:
                raise _StopLoop

        monkeypatch.setattr(check, "time", SimpleNamespace(sleep=fake_sleep))

        with pytest.raises(_StopLoop):
            check.process_download_queue()
        assert done, "the batch never finished"
        return app

    return run


def _cell(app, row):
    return app.table.cells[(str(row["index"]), "download_cart")].plain


def test_size_skipped_item_is_skipped_not_downloaded(run_queue):
    row = _row(0, 1)
    app = run_queue([row], {1: SIZE_SKIPPED})
    assert row["download_cart"] == "[skipped]"
    assert _cell(app, row) == "[skipped]"
    assert row["downloaded"] is False


def test_downloaded_item_is_marked_downloaded(run_queue):
    row = _row(0, 1)
    app = run_queue([row], {1: DOWNLOADED})
    assert row["download_cart"] == "[downloaded]"
    assert _cell(app, row) == "[downloaded]"
    assert row["downloaded"] is True


def test_failed_item_is_failed_not_downloaded(run_queue):
    row = _row(0, 1)
    app = run_queue([row], {1: FAILED})
    assert row["download_cart"] == "[failed]"
    assert _cell(app, row) == "[failed]"
    assert row["downloaded"] is False


def test_stats_count_a_skipped_item_as_missing(run_queue):
    rows = [_row(0, 1), _row(1, 2), _row(2, 3)]
    app = run_queue(rows, {1: SIZE_SKIPPED, 2: DOWNLOADED, 3: FAILED})
    text = app.nodes["#db_info_bar"].text
    assert "[DL'd: 1]" in text
    assert "[Missing: 2]" in text
    assert "[Unique Missing: 2]" in text


def test_downloaded_false_filter_keeps_a_skipped_item(run_queue):
    rows = [_row(0, 1), _row(1, 2)]
    app = run_queue(rows, {1: SIZE_SKIPPED, 2: DOWNLOADED})
    # Only "Downloaded False" ticked in the filter
    app.nodes["#downloaded"] = SimpleNamespace(compare=lambda value: value == "False")
    app._filter_runner()
    assert [r["media_id"] for r in app._filtered_rows] == [1]


@pytest.mark.parametrize(
    "action",
    [
        "action_select_all_undownloaded",
        "action_select_page_undownloaded",
        "action_select_current_page",
        "action_select_all_filtered",
        "action_select_unique_all_filtered",
    ],
)
def test_add_actions_re_add_a_skipped_item_like_a_failed_one(run_queue, action):
    rows = [_row(0, 1), _row(1, 2), _row(2, 3)]
    app = run_queue(rows, {1: SIZE_SKIPPED, 2: FAILED, 3: DOWNLOADED})
    getattr(app, action)()
    assert rows[0]["download_cart"] == "[added]"
    assert rows[1]["download_cart"] == "[added]"


def test_add_new_still_leaves_a_downloaded_item_alone(run_queue):
    rows = [_row(0, 1), _row(1, 2)]
    app = run_queue(rows, {1: SIZE_SKIPPED, 2: DOWNLOADED})
    app.action_select_all_undownloaded()
    assert rows[0]["download_cart"] == "[added]"
    assert rows[1]["download_cart"] == "[downloaded]"


class _FakeDataTable:
    id = "data_table"
    ordered_columns_keys = ["download_cart"]

    def __init__(self):
        self.updated = []

    def update_cell_at_coord(self, coord, value):
        self.updated.append(value.plain)


def _click_cart_cell(app, row):
    table = _FakeDataTable()
    event = SimpleNamespace(
        control=table,
        coordinate=SimpleNamespace(column=0),
        cell_key=SimpleNamespace(row_key=SimpleNamespace(value=str(row["index"]))),
    )
    app.on_data_table_cell_selected(event)
    return table.updated


@pytest.mark.parametrize("result,state", [(SIZE_SKIPPED, "[skipped]"), (FAILED, "[failed]")])
def test_clicking_a_skipped_or_failed_cell_adds_it_to_the_cart(run_queue, result, state):
    row = _row(0, 1)
    app = run_queue([row], {1: result})
    assert row["download_cart"] == state
    assert _click_cart_cell(app, row) == ["[added]"]
    assert row["download_cart"] == "[added]"


def test_a_skipped_item_is_sent_again_only_after_it_is_re_added(run_queue):
    row = _row(0, 1)
    app = run_queue([row], {1: SIZE_SKIPPED})
    # The download run doesn't put the skipped row back on the queue
    assert table_app.row_queue.empty()
    # Nor does pressing download with nothing in the cart
    app.add_to_row_queue()
    assert table_app.row_queue.empty()
    assert row["download_cart"] == "[skipped]"
    # Re-adding it and pressing download sends it once
    _click_cart_cell(app, row)
    app.add_to_row_queue()
    assert row["download_cart"] == "[downloading]"
    assert table_app.row_queue.get_nowait() == ("0", row)
    assert table_app.row_queue.empty()


# --- #358: the Downloaded cell is redrawn with the download cell ---


@pytest.mark.parametrize(
    "result,state,downloaded",
    [
        (DOWNLOADED, "[downloaded]", "True"),
        (SIZE_SKIPPED, "[skipped]", "False"),
        (FAILED, "[failed]", "False"),
    ],
)
def test_downloaded_cell_is_redrawn_with_the_result(
    run_queue, result, state, downloaded
):
    row = _row(0, 1)
    app = run_queue([row], {1: result})
    assert _cell(app, row) == state
    assert app.table.cells[("0", "downloaded")].plain == downloaded


class _AnySettings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _full_row(index, media_id):
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
        "mediatype": "Images",
        "post_date": "2024-01-01",
        "media": 1,
        "length": "N/A",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + media_id,
        "media_id": media_id,
        "text": "t",
    }


def test_rendered_downloaded_column_is_right_straight_after_the_run(monkeypatch):
    """The real InputApp, driven headless: Add Page, Send Downloads, and the
    real worker thread; the Downloaded cells are read without a redraw."""
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _AnySettings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    rows = [_full_row(1, 11), _full_row(2, 12), _full_row(3, 13)]
    done = _fake_download(
        monkeypatch, rows, {11: DOWNLOADED, 12: SIZE_SKIPPED, 13: FAILED}
    )

    def fake_sleep(seconds):
        if done:
            raise _StopLoop
        time.sleep(0.02)

    monkeypatch.setattr(check, "time", SimpleNamespace(sleep=fake_sleep))
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())

    def worker():
        try:
            check.process_download_queue()
        except _StopLoop:
            pass

    async def drive():
        app = table_app.InputApp()
        app.table_data = rows
        app._sortkey = None
        app._reverse = False
        monkeypatch.setattr(table_app, "app", app, raising=False)
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        async with app.run_test(size=(260, 70)) as pilot:
            await pilot.pause()
            await pilot.press("a")  # Add Page
            await pilot.pause()
            app.query_one("#send_downloads_main").press()
            for _ in range(200):
                await pilot.pause(0.05)
                if done:
                    break
            thread.join(5)
            await pilot.pause()
            table = app.table
            return {
                key: (
                    table.get_cell(key, "download_cart").plain,
                    table.get_cell(key, "downloaded").plain,
                )
                for key in ("1", "2", "3")
            }, thread.is_alive()

    rendered, alive = asyncio.run(drive())
    assert not alive
    assert rendered == {
        "1": ("[downloaded]", "True"),
        "2": ("[skipped]", "False"),
        "3": ("[failed]", "False"),
    }
