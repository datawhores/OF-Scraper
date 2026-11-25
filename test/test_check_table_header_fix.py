import asyncio
import queue
from types import SimpleNamespace

import pytest

import ofscraper.classes.table.app as table_app
import ofscraper.classes.table.utils.post_metrics as post_metrics

LONG_ID = 123456789012345678


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


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
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )


def _media_row(index, **values):
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


def _media_obj(mid, pid, mtype="images", canview=True):
    return SimpleNamespace(
        id=mid,
        post_id=pid,
        mediatype=mtype,
        numeric_duration=None,
        duration=None,
        canview=canview,
    )


def _post_obj(pid, price, items, date="2024-05-01 12:00:00"):
    return SimpleNamespace(
        id=pid,
        price=price,
        opened=1,
        all_media=items,
        responsetype="timeline",
        formatted_date=date,
        db_sanitized_text="post",
    )


def _app(media_rows, post_rows):
    app = table_app.InputApp()
    app.table_data = media_rows
    app.post_data = post_rows
    app._sortkey = None
    app._reverse = False
    return app


LONG_NAME = "a_long_creator_x"  # 16 characters


def test_long_values_stay_on_one_line(stub_env):
    # columns narrower than the old 18 (media) and 16 (posts) wrapped these
    # values onto a second line, doubling the row height
    media_rows = [
        _media_row(
            1,
            post_id=LONG_ID,
            media_id=LONG_ID,
            post_date="2024-05-01",
            username=LONG_NAME,
        ),
        _media_row(2, post_date="Probably Deleted"),
    ]
    post_rows = post_metrics.build_post_centric_rows(
        [_post_obj(2, 0, [_media_obj(2, 2)])], LONG_NAME, 1
    )

    async def drive():
        app = _app(media_rows, post_rows)
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


def test_new_cost_says_unlocked_for_a_bought_post_and_free_for_a_free_one(monkeypatch):
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )
    free_post = _post_obj(10, 0, [_media_obj(1, 10)])
    bought_post = _post_obj(20, 12.0, [_media_obj(2, 20)])

    free_row, bought_row = post_metrics.build_post_centric_rows(
        [free_post, bought_post], "creator_a", 1
    )

    assert free_row["new_cost_per_photo"] == "Free"
    assert free_row["new_cost_per_media"] == "Free"
    assert bought_row["new_cost_per_photo"] == "Unlocked"
    assert bought_row["new_cost_per_media"] == "Unlocked"


@pytest.mark.parametrize("field", ["#minDate", "#maxDate"])
@pytest.mark.parametrize("bound", ["2025.13.45", "01/02/2025", "soon"])
def test_an_unreadable_date_bound_does_not_hide_rows(stub_env, field, bound):
    media_rows = [
        _media_row(1, post_date="2024-05-01 12:00:00"),
        _media_row(2, post_date="Probably Deleted"),
    ]

    async def drive():
        app = _app(media_rows, [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            app.query_one(field).value = bound
            app.set_filtered_rows()
            assert [r["index"] for r in app._filtered_rows] == [1, 2]

    asyncio.run(drive())


def test_a_readable_date_bound_still_filters(stub_env):
    media_rows = [
        _media_row(1, post_date="2024-05-01 12:00:00"),
        _media_row(2, post_date="2026-05-01 12:00:00"),
        _media_row(3, post_date="Probably Deleted"),
    ]

    async def drive():
        app = _app(media_rows, [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            app.query_one("#minDate").value = "2025.01.01"
            app.set_filtered_rows()
            assert [r["index"] for r in app._filtered_rows] == [2]

    asyncio.run(drive())


@pytest.mark.parametrize(
    "now, posted",
    [
        # east of UTC in the afternoon: today's local midnight is yesterday in UTC
        ("2026-03-10T15:00:00+10:00", "2026-03-10 03:00:00"),
        # west of UTC in the evening: the post's UTC date is already tomorrow
        ("2026-03-10T20:00:00-05:00", "2026-03-11 00:30:00"),
    ],
)
def test_an_earliest_date_alone_keeps_todays_posts(stub_env, monkeypatch, now, posted):
    import ofscraper.classes.table.fields.datefield as datefield

    fixed = datefield.arrow.get(now)
    monkeypatch.setattr(datefield.arrow, "now", lambda *a, **k: fixed)
    media_rows = [_media_row(1, post_date=posted)]

    async def drive():
        app = _app(media_rows, [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            app.query_one("#minDate").value = "2026.03.01"
            app.set_filtered_rows()
            assert [r["index"] for r in app._filtered_rows] == [1]

    asyncio.run(drive())


@pytest.mark.parametrize(
    "length",
    ["1 day, 1:00:00", "2 days, 0:00:05", "1:30:00.500000"],
)
def test_long_and_fractional_lengths_pass_a_length_filter(stub_env, length):
    # str(timedelta) adds "N day(s), " from 24 hours and a fraction for
    # non-whole seconds; neither was read, so any length filter hid the row
    media_rows = [_media_row(1, length=length), _media_row(2, length="0:10:00")]

    async def drive():
        app = _app(media_rows, [])
        async with app.run_test(size=(250, 60)) as pilot:
            await pilot.pause()
            app.query_one("#length").query_one("#min_hour").value = "1"
            app.set_filtered_rows()
            assert [r["index"] for r in app._filtered_rows] == [1]

    asyncio.run(drive())