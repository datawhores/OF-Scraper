"""ID filters accept pasted numbers and the downloader's temp filenames."""

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


def _drive(monkeypatch, steps):
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

    _drive(monkeypatch, steps)


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

    _drive(monkeypatch, steps)


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

    _drive(monkeypatch, steps)


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

    _drive(monkeypatch, steps)


def test_other_numeric_input_paste_is_unchanged(monkeypatch):
    async def steps(app, pilot):
        box = app.query_one("#post_media_count_input", Input)
        box.post_message(Paste(" 123 "))
        await pilot.pause()
        assert box.value == ""
        app.notify.assert_not_called()

    _drive(monkeypatch, steps)
