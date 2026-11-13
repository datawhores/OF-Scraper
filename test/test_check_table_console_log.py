"""Check table: logging after the table has closed doesn't raise.

The table's console page shows the "shared" log through a TextHandler. Once
the console page had been on screen (Send Downloads switches to it), the
handler kept writing to it after the app exited, and RichLog.write raised
NoActiveAppError: the "Finished Script" message at exit crashed the run,
and a download still running in the worker thread would have stopped at its
next log line.
"""

import asyncio
import logging
import queue
import threading
from types import SimpleNamespace

import ofscraper.classes.table.app as table_app
from ofscraper.utils.logs.classes.handlers.text import TextHandler


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def test_logging_after_the_table_closes(monkeypatch):
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
