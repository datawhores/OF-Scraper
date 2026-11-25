import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.coordinate import Coordinate
from textual.widgets import ContentSwitcher, Input

import ofscraper.classes.table.app as table_app
import ofscraper.classes.table.utils.post_metrics as post_metrics


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _media_obj(mid, pid, mtype, duration=None, canview=None):
    return SimpleNamespace(
        id=mid,
        post_id=pid,
        mediatype=mtype,
        numeric_duration=duration,
        duration=duration,
        canview=canview,
    )


def _post_obj(pid, price, opened, items, date="2024-05-01 12:00:00", text="bundle"):
    # unless a test says otherwise, an item can be viewed when its post is
    # bought or free, as OnlyFans reports it for a current subscription
    for m in items:
        if m.canview is None:
            m.canview = bool(opened) or price == 0
    return SimpleNamespace(
        id=pid,
        price=price,
        opened=opened,
        all_media=items,
        responsetype="timeline",
        formatted_date=date,
        db_sanitized_text=text,
    )


def test_build_post_centric_rows_all_vs_new_metrics(monkeypatch):
    # Media 1 is already downloaded in DB; Media 2 is in a free unlocked post
    monkeypatch.setattr(
        post_metrics,
        "get_media_ids_downloaded_model_sync",
        lambda **k: {1},
    )

    free_post = _post_obj(
        10,
        price=0,
        opened=1,
        items=[_media_obj(2, 10, "images")],
        text="free teaser",
    )
    # Mixed locked bundle: $20 for 2 photos (one is media 2 dupe) + 2 videos (60s dupe media 1 + 40s new media 3)
    bundle_post = _post_obj(
        20,
        price=20.0,
        opened=0,
        items=[
            _media_obj(1, 20, "videos", "0:01:00"),
            _media_obj(2, 20, "images"),
            _media_obj(3, 20, "videos", "0:00:40"),
            _media_obj(4, 20, "images"),
        ],
        text="mixed bundle",
    )
    # Re-send bundle where all media are already downloaded/free
    dupe_post = _post_obj(
        30,
        price=15.0,
        opened=0,
        items=[_media_obj(1, 30, "videos", "0:01:00"), _media_obj(2, 30, "images")],
        text="all dupes",
    )

    rows = post_metrics.build_post_centric_rows(
        [free_post, bundle_post, dupe_post], username="creator_a", model_id=99
    )
    assert len(rows) == 3

    # Photo-only free post
    r0 = rows[0]
    assert r0["video_length"] == "0:00:00"
    assert r0["new_video_length"] == "0:00:00"
    assert r0["cost_per_vid_sec"] == "N/A"
    assert r0["new_cost_per_vid_sec"] == "N/A"
    assert r0["cost_per_photo"] == "$0.00"
    assert r0["new_cost_per_photo"] == "Free"

    # Mixed $20 bundle: All = 4 media (2 photos, 100s video); New = 2 media (1 photo, 40s video)
    r1 = rows[1]
    assert (r1["total_media"], r1["new_media"]) == (4, 2)
    assert (r1["photos"], r1["new_photos"]) == (2, 1)
    assert (r1["videos"], r1["new_videos"]) == (2, 1)
    assert (r1["video_length"], r1["new_video_length"]) == ("0:01:40", "0:00:40")
    assert (r1["cost_per_vid_sec"], r1["new_cost_per_vid_sec"]) == ("$0.20/s", "$0.50/s")
    assert (r1["cost_per_photo"], r1["new_cost_per_photo"]) == ("$10.00", "$20.00")
    assert (r1["cost_per_media"], r1["new_cost_per_media"]) == ("$5.00", "$10.00")

    # All-dupes $15 bundle
    r2 = rows[2]
    assert r2["new_media"] == 0
    assert r2["new_video_length"] == "0:00:00"
    assert r2["new_cost_per_vid_sec"] == "All Dupes"
    assert r2["new_cost_per_photo"] == "All Dupes"
    assert r2["new_cost_per_media"] == "All Dupes"


@pytest.fixture
def stub_env(monkeypatch, tmp_path):
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


def _media_row(index, post_id, media_id, unlocked=True):
    return {
        "index": index,
        "number": index,
        "download_cart": "[]" if unlocked else "Not Unlocked",
        "username": "creator_a",
        "downloaded": False,
        "unlocked": unlocked,
        "download_type": "normal",
        "other_posts_with_media": [],
        "post_media_count": 2,
        "mediatype": "Videos",
        "post_date": "2024-05-01",
        "media": 2,
        "length": "0:01:00",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": post_id,
        "media_id": media_id,
        "text": f"post {post_id}",
    }


def test_post_table_cart_sync_filters_and_inspect(stub_env, monkeypatch):
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    p1 = _post_obj(101, 0, 1, [_media_obj(1, 101, "videos", "0:01:00"), _media_obj(2, 101, "images")], text="unlocked bundle")
    p2 = _post_obj(102, 10, 0, [_media_obj(3, 102, "videos", "0:02:00")], text="locked ppv")
    p_rows = post_metrics.build_post_centric_rows([p1, p2], "creator_a", 1)
    m_rows = [
        _media_row(1, 101, 1, unlocked=True),
        _media_row(2, 101, 2, unlocked=True),
        _media_row(3, 102, 3, unlocked=False),
    ]

    async def drive():
        app = table_app.InputApp()
        app.table_data = m_rows
        app.post_data = p_rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            # Switch to PostTable tab
            await pilot.click("#post_tab")
            await pilot.pause()
            assert app.query_one(ContentSwitcher).current == "post_table_page"
            assert app.post_table.row_count == 2

            # Toggle unlocked post 101 into cart via Enter on Number cell
            app.post_table.focus()
            app.post_table.cursor_coordinate = Coordinate(0, 0)
            await pilot.press("enter")
            await pilot.pause()
            assert [r["download_cart"] for r in m_rows] == ["[added]", "[added]", "Not Unlocked"]
            assert p_rows[0]["download_cart"] == "[added (2/2)]"

            # Locked post 102 cannot be added
            app.post_table.cursor_coordinate = Coordinate(1, 0)
            await pilot.press("enter")
            await pilot.pause()
            assert m_rows[2]["download_cart"] == "Not Unlocked"

            # Post-only sidebar filter: filter to unlocked only
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert app.query_one("#post_options_sidebar").has_class("-show")
            app.query_one("#post_unlocked").select_true()
            await pilot.click("#post_filter")
            await pilot.pause()
            assert len(app._filtered_post_rows) == 1
            assert app._filtered_post_rows[0]["post_id"] == 101

            # Press f to inspect post 101 media in MediaTable
            app.post_table.focus()
            app.post_table.cursor_coordinate = Coordinate(0, 0)
            await pilot.press("f")
            await pilot.pause()
            assert app.query_one(ContentSwitcher).current == "media_table_page"
            assert app.query_one("#post_id_input", Input).value == "101"
            assert [r["post_id"] for r in app._filtered_rows] == [101, 101]

    asyncio.run(drive())


def test_post_media_filter_and_header_widths(stub_env, monkeypatch):
    from textual.widgets import SelectionList

    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    p_vid = _post_obj(201, 5, 1, [_media_obj(11, 201, "videos", "0:01:00")], text="video only")
    p_pic = _post_obj(202, 5, 1, [_media_obj(12, 202, "images")], text="photo only")
    p_mix = _post_obj(
        203, 10, 1,
        [_media_obj(13, 203, "videos", "0:02:00"), _media_obj(14, 203, "images")],
        text="mixed video + photo",
    )
    p_rows = post_metrics.build_post_centric_rows([p_vid, p_pic, p_mix], "creator_a", 1)

    async def drive():
        app = table_app.InputApp()
        app.table_data = []
        app.post_data = p_rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            await pilot.click("#post_tab")
            await pilot.pause()

            # 1. Column widths fit every header including sort indicator
            for col in app.post_table.ordered_columns:
                assert col.width >= max(len(line) for line in col.label.plain.splitlines()) + 2

            # 2. Default: nothing selected -> all 3 posts shown
            sel = app.query_one("#post_mediatype").query_one(SelectionList)
            assert list(sel.selected) == []
            assert [r["post_id"] for r in app._filtered_post_rows] == [201, 202, 203]

            # 3. Select Videos -> posts with >= 1 video (201 and 203)
            await pilot.press("ctrl+s")
            await pilot.pause()
            sel.select("Videos")
            await pilot.click("#post_filter")
            await pilot.pause()
            assert [r["post_id"] for r in app._filtered_post_rows] == [201, 203]

            # 4. Select Videos + Images -> posts with >= 1 video AND >= 1 image (only 203)
            await pilot.press("ctrl+s")
            await pilot.pause()
            sel.select("Images")
            await pilot.click("#post_filter")
            await pilot.pause()
            assert [r["post_id"] for r in app._filtered_post_rows] == [203]

            # 5. Select all 3 (Videos + Images + Audios) -> nets 0 posts
            await pilot.press("ctrl+s")
            await pilot.pause()
            sel.select("Audios")
            await pilot.click("#post_filter")
            await pilot.pause()
            assert app._filtered_post_rows == []

            # 6. Clear Filters resets selection to empty and restores all 3 posts
            await pilot.press("ctrl+s")
            await pilot.pause()
            await pilot.click("#post_clear_filters")
            await pilot.pause()
            assert list(sel.selected) == []
            assert [r["post_id"] for r in app._filtered_post_rows] == [201, 202, 203]

    asyncio.run(drive())


def test_post_audio_columns_hidden_by_default_and_columns_tab_v(stub_env, monkeypatch):
    from types import SimpleNamespace
    cache_store = {}
    monkeypatch.setattr(
        table_app,
        "cache",
        SimpleNamespace(
            get=lambda k, default=None: cache_store.get(k, default),
            set=lambda k, v: cache_store.__setitem__(k, v),
        ),
    )
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    p_aud = _post_obj(301, 12.0, 0, [_media_obj(21, 301, "audios", "0:02:00")], text="audio track")
    p_rows = post_metrics.build_post_centric_rows([p_aud], "creator_a", 1)
    assert p_rows[0]["audios"] == 1
    assert p_rows[0]["new_audios"] == 1
    assert p_rows[0]["audio_length"] == "0:02:00"
    assert p_rows[0]["cost_per_audio"] == "$12.00"
    assert p_rows[0]["new_cost_per_audio_sec"] == "$0.10/s"

    async def drive():
        app = table_app.InputApp()
        app.table_data = []
        app.post_data = p_rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            await pilot.click("#post_tab")
            await pilot.pause()

            hidden_cols = {"audios", "new_audios", "audio_length", "new_audio_length", "cost_per_audio", "new_cost_per_audio"}
            assert set(app.post_table.ordered_columns_keys) & hidden_cols == set()
            assert "post_id" not in app.table.ordered_columns_keys

            # Pressing h reveals extra columns on MediaTable (including post_id)
            # without adding audio columns to PostTable
            await pilot.press("h")
            await pilot.pause()
            assert "post_id" in app.table.ordered_columns_keys
            assert set(app.post_table.ordered_columns_keys) & hidden_cols == set()

            # Click Columns (v) button on PostTable to open picker, enable Post Audio columns, and press v to return (session-only)
            await pilot.click("#open_columns_post")
            await pilot.pause()
            assert app.query_one(ContentSwitcher).current == "columns_page"
            await pilot.click("#toggle_post_audio_cols")
            await pilot.pause()
            await pilot.press("v")
            await pilot.pause()
            assert app.query_one(ContentSwitcher).current == "post_table_page"
            assert hidden_cols <= set(app.post_table.ordered_columns_keys)
            assert app.post_table.get_cell("1", "audios").plain == "1"
            assert app.post_table.get_cell("1", "audio_length").plain == "0:02:00"
            assert table_app.cache.get(table_app.POST_COLS_CACHE_KEY, default=None) is None

            # Save as Default persists the selection to cache
            await pilot.click("#columns_tab")
            await pilot.pause()
            await pilot.click("#save_default_columns")
            await pilot.pause()
            saved_post = table_app.cache.get(table_app.POST_COLS_CACHE_KEY, default=None)
            assert saved_post is not None and hidden_cols <= set(saved_post)

            # Reset Defaults in Columns tab clears saved default and removes audio columns again
            await pilot.click("#reset_columns")
            await pilot.pause()
            assert table_app.cache.get(table_app.POST_COLS_CACHE_KEY, default=None) is None
            await pilot.click("#apply_columns")
            await pilot.pause()
            assert set(app.post_table.ordered_columns_keys) & hidden_cols == set()

    asyncio.run(drive())


def test_media_default_columns_and_protected_download_type(stub_env):
    # a locked item with no link shows "protected", but only on screen: the
    # row keeps "unknown", which the filters and the cart guards test for
    sample_row = {
        "index": 1,
        "number": 1,
        "download_cart": "Not Unlocked",
        "username": "creator_a",
        "downloaded": False,
        "unlocked": False,
        "download_type": "unknown",
        "other_posts_with_media": [],
        "length": "0:01:00",
        "mediatype": "videos",
        "post_date": "2026-01-01",
        "post_media_count": 1,
        "responsetype": "Timeline",
        "price": "$10.00",
        "post_id": 501,
        "media_id": 901,
        "text": "locked video",
    }

    # an unlocked item with no link is not protected, just unknown
    open_row = dict(
        sample_row,
        index=2,
        number=2,
        download_cart="Unknown",
        unlocked=True,
        media_id=902,
    )

    async def drive():
        app = table_app.InputApp()
        app.table_data = [sample_row, open_row]
        app.post_data = []
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()

            # this fork's defaults (#470): ids and details hidden, type shown
            visible_default = set(app.table.ordered_columns_keys)
            assert not {"post_id", "media_id", "responsetype"} & visible_default
            assert "download_type" in visible_default

            assert app.table.get_cell("1", "download_type").plain == "protected"
            assert app.table.get_cell("2", "download_type").plain == "unknown"
            assert sample_row["download_type"] == "unknown"
            assert open_row["download_type"] == "unknown"

    asyncio.run(drive())


def test_post_table_latest_date_filter_visible_and_works(stub_env, monkeypatch):
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    p_old = _post_obj(401, 5.0, 0, [_media_obj(31, 401, "images")], text="older post")
    p_old.formatted_date = "2025-01-10"
    p_new = _post_obj(402, 5.0, 0, [_media_obj(32, 402, "images")], text="newer post")
    p_new.formatted_date = "2026-06-15"
    p_rows = post_metrics.build_post_centric_rows([p_old, p_new], "creator_a", 1)

    async def drive():
        app = table_app.InputApp()
        app.table_data = []
        app.post_data = p_rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            await pilot.click("#post_tab")
            await pilot.pause()

            # Open PostTable sidebar and check both Earliest and Latest Date inputs render side-by-side
            await pilot.press("ctrl+s")
            await pilot.pause()
            min_input = app.query_one("#post_post_date_minDate")
            max_input = app.query_one("#post_post_date_maxDate")
            assert min_input.region.width > 0
            assert max_input.region.width > 0
            assert max_input.region.x >= min_input.region.right

            # Filter to Latest Date = 2025.12.31 -> only older post remains
            max_input.value = "2025.12.31"
            await pilot.click("#post_filter")
            await pilot.pause()
            assert [r["post_id"] for r in app._filtered_post_rows] == [401]

    asyncio.run(drive())


# --- fixes made while bringing upstream #685 in ---


class _CountingRows(list):
    """Media rows that count how often they are walked through."""

    def __init__(self, rows):
        super().__init__(rows)
        self.walks = 0

    def __iter__(self):
        self.walks += 1
        return super().__iter__()


def test_post_cart_sync_walks_the_media_rows_once(stub_env, monkeypatch):
    # walking every media row for every post took 15 s at startup with 6,000
    # posts and 18,000 media rows
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    posts = [
        _post_obj(1000 + n, 0, 1, [_media_obj(n, 1000 + n, "images")])
        for n in range(1, 51)
    ]
    app = table_app.InputApp()
    app.post_data = post_metrics.build_post_centric_rows(posts, "creator_a", 1)
    app.table_data = _CountingRows(
        [_media_row(n, 1000 + n, n) for n in range(1, 51)]
    )
    app.table_data[0]["download_cart"] = "[added]"

    app.sync_post_cart_states()

    assert app.table_data.walks == 1
    assert app.post_data[0]["download_cart"] == "[added (1/1)]"
    assert {r["download_cart"] for r in app.post_data[1:]} == {"[]"}


def test_a_post_that_cannot_be_viewed_is_locked_even_when_free(monkeypatch):
    # an expired subscription: the post is free, but OnlyFans says canView
    # false for its media
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    free_hidden = _post_obj(
        10, 0, 0, [_media_obj(1, 10, "images", canview=False)], text="free"
    )
    paid = _post_obj(
        20,
        12.0,
        0,
        [_media_obj(1, 20, "images"), _media_obj(2, 20, "images")],
        text="paid",
    )

    rows = post_metrics.build_post_centric_rows([free_hidden, paid], "creator_a", 1)

    assert rows[0]["unlocked"] is False
    assert rows[0]["download_cart"] == "Not Unlocked"
    # media 1 isn't owned, so the paid post's two photos are both new
    assert rows[1]["new_media"] == 2
    assert rows[1]["new_cost_per_media"] == "$6.00"


def test_a_free_preview_counts_as_owned_but_leaves_its_post_locked(monkeypatch):
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    teaser = _post_obj(
        30,
        10.0,
        0,
        [
            _media_obj(5, 30, "images", canview=True),
            _media_obj(6, 30, "videos", "0:00:10", canview=False),
        ],
    )

    row = post_metrics.build_post_centric_rows([teaser], "creator_a", 1)[0]

    assert row["unlocked"] is False
    assert (row["total_media"], row["new_media"]) == (2, 1)


def test_sorting_posts_by_number_keeps_each_creator_together(monkeypatch):
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    rows = []
    for name, first in (("creator_a", 100), ("creator_b", 200)):
        posts = [
            _post_obj(first + n, 0, 1, [_media_obj(first + n, first + n, "images")])
            for n in range(3)
        ]
        rows.extend(
            post_metrics.build_post_centric_rows(
                posts, name, 1, start_index=len(rows) + 1
            )
        )
    app = table_app.InputApp()
    app.post_data = list(reversed(rows))

    app._post_reverse = False
    app._post_sort_runner("number")
    assert [(r["username"], r["number"]) for r in app.post_data] == [
        ("creator_a", 1),
        ("creator_a", 2),
        ("creator_a", 3),
        ("creator_b", 1),
        ("creator_b", 2),
        ("creator_b", 3),
    ]


def test_h_hides_saved_extra_columns_on_the_first_press(stub_env, monkeypatch):
    # Save as Default stored the extra columns as showing while the h flag
    # still said hidden, so the first h press added columns already there
    cache_store = {
        table_app.MEDIA_COLS_CACHE_KEY: list(table_app.get_col_names(show_extra=True)),
        table_app.EXTRA_COLUMNS_CACHE_KEY: False,
    }
    monkeypatch.setattr(
        table_app,
        "cache",
        SimpleNamespace(
            get=lambda k, default=None: cache_store.get(k, default),
            set=lambda k, v: cache_store.__setitem__(k, v),
        ),
    )

    async def drive():
        app = table_app.InputApp()
        app.table_data = [_media_row(1, 101, 1)]
        app.post_data = []
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            assert table_app.EXTRA_COLUMNS <= set(app.table.ordered_columns_keys)
            await pilot.press("h")
            await pilot.pause()
            assert not table_app.EXTRA_COLUMNS & set(app.table.ordered_columns_keys)

    asyncio.run(drive())


def test_posts_tab_hint_offers_only_keys_that_work_there(stub_env):
    # o opens a folder from the media tab only
    async def drive():
        app = table_app.InputApp()
        app.table_data = []
        app.post_data = []
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            hint = str(app.query_one("#post_table_instructions").render())
            assert "(f)" in hint
            assert "(o)" not in hint

    asyncio.run(drive())
