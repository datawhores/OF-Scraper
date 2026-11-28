"""Check-table filter sidebar, username/ID/length filters, and cell shortcuts."""

# ----------------------------------------------------------------------
# From test_check_filters_419.py
# Check-table cell shortcuts and inclusive length filters (#419).
# ----------------------------------------------------------------------

import asyncio
import queue
from types import SimpleNamespace

import pytest
from textual.widgets import Input, Label, SelectionList

import ofscraper.classes.table.app as table_app
import ofscraper.classes.table.utils.post_metrics as post_metrics


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


@pytest.fixture
def table_env(monkeypatch, tmp_path, request):
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
    monkeypatch.setattr(table_app.cache, "get", lambda *a, **k: True)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())
    monkeypatch.setattr(
        post_metrics, "get_media_ids_downloaded_model_sync", lambda **k: set()
    )


def _row(index, **values):
    row = dict(
        index=index, number=index, download_cart="[]", username="a_creator",
        downloaded=False, unlocked=True, download_type="normal",
        other_posts_with_media=[], length="0:01:30", mediatype="Videos",
        post_date="2024-01-01", post_media_count=1, media=1,
        responsetype="Timeline", price="Free", post_id=100 + index,
        media_id=1000 + index, text="t",
    )
    row.update(values)
    return row


async def _settle(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


def _drive(rows, steps, *, post_rows=None, size=(245, 60)):
    async def run():
        app = table_app.InputApp()
        app.table_data = rows
        if post_rows is not None:
            app.post_data = post_rows
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(app, pilot)

    asyncio.run(run())


@pytest.mark.usefixtures("table_env")
def test_username_cell_semicolon_copies_to_filter():
    async def steps(app, pilot):
        app.table.move_cursor(
            row=0, column=app.table.ordered_columns_keys.index("username")
        )
        app.table.focus()
        await pilot.press(";")
        assert app.query_one("#username").value == "a_creator"

    _drive([_row(1)], steps)


@pytest.mark.usefixtures("table_env")
def test_response_cell_semicolon_selects_its_option():
    responses = [
        "Timeline", "Archived", "Pinned", "Streams", "Stories", "Highlights",
        "Messages", "Stream", "Story", "Highlight", "Message",
    ]
    aliases = {
        "Stream": "Streams", "Story": "Stories",
        "Highlight": "Highlights", "Message": "Messages",
    }
    rows = [_row(i, responsetype=r) for i, r in enumerate(responses, 1)]

    async def steps(app, pilot):
        col = app.table.ordered_columns_keys.index("responsetype")
        for idx, response in enumerate(responses):
            app.table_data = [rows[idx]]
            app.set_filtered_rows()
            app.reset_table()
            await pilot.pause()
            app.table.move_cursor(row=0, column=col)
            app.table.focus()
            await pilot.press(";")
            selected = app.query_one("#responsetype").query_one(SelectionList).selected
            assert selected == [aliases.get(response, response)]
            app.set_filtered_rows()
            assert [r["index"] for r in app._filtered_rows] == [idx + 1]

    _drive([rows[0]], steps)


@pytest.mark.usefixtures("table_env")
def test_length_filter_includes_bounds():
    cases = [
        ("0:01:00", None, [2, 3, 4, 5]),
        (None, "0:02:00", [1, 2, 3, 4]),
        ("0:01:00", "0:02:00", [2, 3, 4]),
    ]
    rows = [
        _row(index, length=length)
        for index, length in enumerate(
            ["0:00:30", "0:01:00", "0:01:30", "0:02:00", "0:02:30"], 1
        )
    ]

    async def steps(app, pilot):
        field = app.query_one("#length")
        for start, end, expected in cases:
            field.reset()
            if start is not None:
                field.update_table_min(start)
            if end is not None:
                field.update_table_max(end)
            app.set_filtered_rows()
            assert [row["index"] for row in app._filtered_rows] == expected

    _drive(rows, steps)


# ----------------------------------------------------------------------
# From test_check_table_clear_username.py
# Check table filter sidebar (Ctrl+S): Clear Filters empties the username box.
# ----------------------------------------------------------------------


def test_clear_filters_empties_the_username_box(table_env):
    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        box = app.query_one("#username", Input)
        box.value = "a_creator"
        app.set_filtered_rows()
        await _settle(pilot)
        assert len(app._filtered_rows) == 1

        app.query_one("#clear_filters").press()
        await _settle(pilot)

        assert box.value == ""
        assert len(app._filtered_rows) == 2

    _drive([_row(1, username="a_creator"), _row(2, username="another_creator")], steps)


# ----------------------------------------------------------------------
# From test_check_table_username_partial.py
# Check table filter sidebar (Ctrl+S): the username box matches part of a name.
# ----------------------------------------------------------------------


def test_username_box_matches_part_of_a_name(table_env):
    cases = [
        ("first", ["first_creator"]),  # the start of a name
        ("ST_CRE", ["first_creator"]),  # the middle, any case
        (" creator ", ["first_creator", "second_creator"]),
        ("first_creator", ["first_creator"]),  # a whole name still works
        ("nobody", []),
        ("", ["first_creator", "second_creator"]),
    ]

    async def steps(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        box = app.query_one("#username", Input)
        for typed, shown in cases:
            box.value = typed
            app.set_filtered_rows()
            assert sorted(r["username"] for r in app._filtered_rows) == shown

    _drive(
        [_row(1, username="first_creator"), _row(2, username="second_creator")],
        steps,
    )

# ----------------------------------------------------------------------
# From test_check_table_id_paste.py
# ID filters accept pasted numbers and the downloader's temp filenames.
# ----------------------------------------------------------------------

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from textual.app import App
from textual.events import Paste
from textual.widgets import Input

from ofscraper.classes.table.fields.numfield import NumField
import ofscraper.utils.settings as settings


class _IdApp(App):
    def compose(self):
        yield NumField("Media_ID")
        yield NumField("Post_ID")
        yield NumField("Post_Media_Count")


def _drive_idpaste(monkeypatch, steps):
    monkeypatch.setattr(settings, "get_settings", lambda: SimpleNamespace())

    async def run():
        app = _IdApp()
        app.notify = Mock(wraps=app.notify)
        async with app.run_test() as pilot:
            await steps(app, pilot)

    asyncio.run(run())


@pytest.mark.parametrize("field", ["media_id", "post_id"])
@pytest.mark.parametrize(
    "text",
    [
        "3456789012",
        " 3456789012",
        "3456789012 ",
        "3456789012\t",
        "\n\t3456789012\r\n",
    ],
)
def test_id_paste_number(monkeypatch, field, text):
    async def steps(app, pilot):
        box = app.query_one(f"#{field}_input", Input)
        box.post_message(Paste(text))
        await pilot.pause()
        assert box.value == "3456789012"
        app.notify.assert_not_called()

    _drive_idpaste(monkeypatch, steps)


@pytest.mark.parametrize(
    "field, expected", [("media_id", "1234567890"), ("post_id", "1098765432")]
)
@pytest.mark.parametrize("prefix", ["tempaudio", "tempvid"])
@pytest.mark.parametrize("directory", ["", "D:\\ofscraper\\<creator>\\Posts\\Videos\\"])
def test_id_paste_temp_filename(monkeypatch, field, expected, prefix, directory):
    async def steps(app, pilot):
        box = app.query_one(f"#{field}_input", Input)
        box.value = "123"
        box.post_message(Paste(f"{directory}{prefix}_1234567890_1098765432.part"))
        await pilot.pause()
        assert box.value == expected
        other = "post_id" if field == "media_id" else "media_id"
        assert app.query_one(f"#{other}_input", Input).value == ""
        app.notify.assert_not_called()

    _drive_idpaste(monkeypatch, steps)


@pytest.mark.parametrize("field", ["media_id", "post_id"])
@pytest.mark.parametrize("text", ["junk text", "1234567890_1098765432", "345\n678"])
def test_id_paste_junk_keeps_value_and_notifies(monkeypatch, field, text):
    async def steps(app, pilot):
        box = app.query_one(f"#{field}_input", Input)
        box.value = "123"
        box.action_select_all()
        box.post_message(Paste(text))
        await pilot.pause()
        assert box.value == "123"
        app.notify.assert_called_once()
        message = app.notify.call_args.args[0].lower()
        assert "number" in message and "temp file name" in message

    _drive_idpaste(monkeypatch, steps)


@pytest.mark.parametrize("field", ["media_id", "post_id"])
def test_id_typing_and_numeric_paste_selection_are_unchanged(monkeypatch, field):
    async def steps(app, pilot):
        box = app.query_one(f"#{field}_input", Input)
        box.focus()
        await pilot.press("1", "2", "x", "3")
        assert box.value == "123"
        box.action_select_all()
        box.post_message(Paste("45"))
        await pilot.pause()
        assert box.value == "45"
        await pilot.press("end")
        box.post_message(Paste("67"))
        await pilot.pause()
        assert box.value == "4567"
        app.notify.assert_not_called()

    _drive_idpaste(monkeypatch, steps)


def test_other_numeric_input_paste_is_unchanged(monkeypatch):
    async def steps(app, pilot):
        box = app.query_one("#post_media_count_input", Input)
        box.post_message(Paste(" 123 "))
        await pilot.pause()
        assert box.value == ""
        app.notify.assert_not_called()

    _drive_idpaste(monkeypatch, steps)


@pytest.mark.parametrize("field", ["media_id", "post_id"])
def test_right_click_pastes_what_the_table_copied(monkeypatch, field):
    async def steps(app, pilot):
        box = app.query_one(f"#{field}_input", Input)
        box.value = "123"
        app.copy_to_clipboard("3456789012")
        assert await pilot.click(f"#{field}_input", button=3)
        await pilot.pause()
        # in place of what was there
        assert box.value == "3456789012"
        app.notify.assert_not_called()

        # several ids aren't one number: the value stays, with a notice
        app.copy_to_clipboard("111, 222")
        assert await pilot.click(f"#{field}_input", button=3)
        await pilot.pause()
        assert box.value == "3456789012"
        app.notify.assert_called_once()

    _drive_idpaste(monkeypatch, steps)


def test_right_click_with_nothing_copied_says_so(monkeypatch):
    async def steps(app, pilot):
        box = app.query_one("#post_id_input", Input)
        box.value = "123"
        assert await pilot.click("#post_id_input", button=3)
        await pilot.pause()
        assert box.value == "123"
        app.notify.assert_called_once()
        assert "paste key" in app.notify.call_args.args[0]

    _drive_idpaste(monkeypatch, steps)


def test_right_click_on_another_numeric_input_pastes_nothing(monkeypatch):
    async def steps(app, pilot):
        box = app.query_one("#post_media_count_input", Input)
        app.copy_to_clipboard("45")
        assert await pilot.click("#post_media_count_input", button=3)
        await pilot.pause()
        assert box.value == ""
        app.notify.assert_not_called()

    _drive_idpaste(monkeypatch, steps)

# ----------------------------------------------------------------------
# From test_check_table_length_units.py
# Check table filter sidebar (Ctrl+S): which Length box is hours, minutes, seconds.
#
# The Min/Max length boxes name their unit only as placeholder text, which a
# value hides, and a saved or picked length filled all three with "0", zeros
# included, so no box said which it was. A zero part is now left empty, so its
# placeholder (Hours/Minutes/Seconds) shows. These tests drive the real
# InputApp.
# ----------------------------------------------------------------------

def _drive_lenunits(steps):
    async def run(app, pilot):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        field = app.query_one("#length")
        app.query_one("#options_sidebar").scroll_to_widget(
            field, animate=False, top=True
        )
        await _settle(pilot)
        await steps(app, pilot, field)

    _drive([_row(1, length="0:01:30")], run)


def _values(app, *ids):
    return [app.query_one(f"#{i}", Input).value for i in ids]


MIN = ("min_hour", "min_minute", "min_second")
MAX = ("max_hour", "max_minute", "max_second")


def test_each_box_names_its_unit(table_env):
    async def steps(app, pilot, field):
        for row in (MIN, MAX):
            assert [app.query_one(f"#{b}", Input).placeholder for b in row] == [
                "Hours (0-23)", "Min (0-59)", "Sec (0-59)",
            ]

    _drive_lenunits(steps)


def test_rows_are_labelled(table_env):
    async def steps(app, pilot, field):
        for container, text in [("#minContainer", "Min length"), ("#maxContainer", "Max length")]:
            label = field.query_one(container).query_one(Label)
            assert str(label.render()) == text

    _drive_lenunits(steps)


def test_row_labels_line_up_with_their_boxes(table_env):
    async def steps(app, pilot, field):
        for container, box in [("#minContainer", "#min_hour"), ("#maxContainer", "#max_hour")]:
            label = field.query_one(container).query_one(Label)
            box = app.query_one(box, Input)
            # the label is as tall as the box and its text sits on the middle
            # line, where the box's own text is
            assert (label.region.y, label.region.height) == (box.region.y, box.region.height)
            assert label.styles.content_align_vertical == "middle"

    _drive_lenunits(steps)


@pytest.mark.parametrize(
    "table_env", [{"length_min": 90, "length_max": 3600}], indirect=True
)
def test_saved_lengths_leave_zero_parts_empty(table_env):
    async def steps(app, pilot, field):
        assert _values(app, *MIN) == ["", "1", "30"]
        assert _values(app, *MAX) == ["1", "", ""]
        # an empty part is the placeholder, still telling you which box it is
        assert app.query_one("#max_minute", Input).placeholder == "Min (0-59)"

    _drive_lenunits(steps)


def test_a_picked_length_leaves_zero_parts_empty(table_env):
    async def steps(app, pilot, field):
        field.update_table_val("0:01:30")
        await _settle(pilot)
        assert _values(app, *MIN) == ["", "1", "30"]
        assert _values(app, *MAX) == ["", "1", "30"]
        # and the filter still matches that length
        assert field.compare("0:01:30")
        assert not field.compare("0:02:00")

    _drive_lenunits(steps)


def test_a_two_part_length_fills_hours_and_minutes(table_env):
    # "1:30" has always filled the boxes as 1 hour 30 minutes
    async def steps(app, pilot, field):
        field.update_table_val("1:30")
        await _settle(pilot)
        assert _values(app, *MIN) == ["1", "30", ""]
        assert _values(app, *MAX) == ["1", "30", ""]

    _drive_lenunits(steps)


# ----------------------------------------------------------------------
# Check table date and length filters: unreadable bounds, an earliest
# date alone, and day-long or fractional lengths.
# ----------------------------------------------------------------------


def test_an_unreadable_date_bound_does_not_hide_rows(table_env):
    media_rows = [
        _row(1, post_date="2024-05-01 12:00:00"),
        _row(2, post_date="Probably Deleted"),
    ]

    async def steps(app, pilot):
        for field in ("#minDate", "#maxDate"):
            box = app.query_one(field)
            for bound in ("2025.13.45", "01/02/2025", "soon"):
                box.value = bound
                app.set_filtered_rows()
                assert [r["index"] for r in app._filtered_rows] == [1, 2]
            box.value = ""

    _drive(media_rows, steps, post_rows=[], size=(250, 60))


def test_a_readable_date_bound_still_filters(table_env):
    media_rows = [
        _row(1, post_date="2024-05-01 12:00:00"),
        _row(2, post_date="2026-05-01 12:00:00"),
        _row(3, post_date="Probably Deleted"),
    ]

    async def steps(app, pilot):
        app.query_one("#minDate").value = "2025.01.01"
        app.set_filtered_rows()
        assert [r["index"] for r in app._filtered_rows] == [2]

    _drive(media_rows, steps, post_rows=[], size=(250, 60))


def test_post_date_filter_excludes_undated_posts_only_with_a_bound(table_env):
    post_rows = [
        _row(1, post_date="2026-05-01"),
        _row(2, post_date="Probably Deleted"),
    ]

    async def steps(app, pilot):
        assert [row["index"] for row in app._filtered_post_rows] == [1, 2]
        app.query_one("#post_post_date_minDate").value = "2025.01.01"
        app.filter_post_table()
        assert [row["index"] for row in app._filtered_post_rows] == [1]

    _drive([], steps, post_rows=post_rows, size=(250, 60))


@pytest.mark.parametrize(
    "now, posted",
    [
        # east of UTC in the afternoon: today's local midnight is yesterday in UTC
        ("2026-03-10T15:00:00+10:00", "2026-03-10 03:00:00"),
        # west of UTC in the evening: the post's UTC date is already tomorrow
        ("2026-03-10T20:00:00-05:00", "2026-03-11 00:30:00"),
    ],
)
def test_an_earliest_date_alone_keeps_todays_posts(table_env, monkeypatch, now, posted):
    import ofscraper.classes.table.fields.datefield as datefield

    fixed = datefield.arrow.get(now)
    monkeypatch.setattr(datefield.arrow, "now", lambda *a, **k: fixed)
    media_rows = [_row(1, post_date=posted)]

    async def steps(app, pilot):
        app.query_one("#minDate").value = "2026.03.01"
        app.set_filtered_rows()
        assert [r["index"] for r in app._filtered_rows] == [1]

    _drive(media_rows, steps, post_rows=[], size=(250, 60))


def test_long_and_fractional_lengths_pass_a_length_filter(table_env):
    # str(timedelta) adds "N day(s), " from 24 hours and a fraction for
    # non-whole seconds; neither was read, so any length filter hid the row
    lengths = ["1 day, 1:00:00", "2 days, 0:00:05", "1:30:00.500000"]
    media_rows = [
        *(_row(i, length=length) for i, length in enumerate(lengths, 1)),
        _row(len(lengths) + 1, length="0:10:00"),
    ]

    async def steps(app, pilot):
        app.query_one("#length").query_one("#min_hour").value = "1"
        app.set_filtered_rows()
        assert [r["index"] for r in app._filtered_rows] == [1, 2, 3]

    _drive(media_rows, steps, post_rows=[], size=(250, 60))


def test_fractional_lengths_above_maximum_are_excluded(table_env):
    rows = [
        _row(1, length="0:01:30"),
        _row(2, length="0:01:30.900000"),
    ]

    async def steps(app, pilot):
        field = app.query_one("#length")
        field.update_table_max("0:01:30")
        app.set_filtered_rows()
        assert [r["index"] for r in app._filtered_rows] == [1]

    _drive(rows, steps, post_rows=[], size=(250, 60))


def test_fractional_length_fills_integer_inputs(table_env):
    async def steps(app, pilot, field):
        field.update_table_val("0:01:30.900000")
        await _settle(pilot)
        assert _values(app, *MIN) == ["", "1", "30"]
        assert _values(app, *MAX) == ["", "1", "31"]
        assert field.compare("0:01:30.900000")

    _drive_lenunits(steps)


@pytest.mark.usefixtures("table_env")
def test_fractional_length_cell_filter_keeps_its_source_row():
    lengths = ["0:01:30.900000", "0:00:59.900000", "1 day, 23:59:59.900000"]
    rows = [_row(i, length=length) for i, length in enumerate(lengths, 1)]

    async def steps(app, pilot):
        col = app.table.ordered_columns_keys.index("length")
        for idx in range(len(lengths)):
            app.table_data = [rows[idx]]
            app.query_one("#length").reset()
            app.set_filtered_rows()
            app.reset_table()
            await pilot.pause()
            app.table.move_cursor(row=0, column=col)
            app.table.focus()
            await pilot.press(";")
            app.set_filtered_rows()
            assert [r["index"] for r in app._filtered_rows] == [idx + 1]

    _drive([rows[0]], steps)
