"""A failed main-menu action says so on screen (#307).

The main menu caught every error and wrote it only to the debug log, so at the
normal output level the menu just came back with no sign that anything failed.
"""

import io
import logging
from types import SimpleNamespace

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.interactive as interactive
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.menu as menu

ERROR_TEXT = r"could not open logs\[old] [bold]x[/bold]"


@pytest.fixture
def screen(monkeypatch):
    """The "shared" logger with the app's real console handlers at the
    normal output level, printing to a buffer; yields that buffer."""
    out = io.StringIO()
    fake_console = Console(file=out, markup=True, width=500, color_system=None)
    monkeypatch.setattr(stdout_logs.console, "get_console", lambda: fake_console)
    monkeypatch.setattr(stdout_logs.console, "get_shared_console", lambda: fake_console)
    monkeypatch.setattr(
        stdout_logs.settings, "get_settings", lambda: SimpleNamespace(output_level="NORMAL")
    )
    logger = logging.getLogger("shared")
    old_handlers, old_level = logger.handlers[:], logger.level
    stdout_logs.add_stdout_handler(logger, clear=True)
    try:
        yield out
    finally:
        logger.handlers[:] = old_handlers
        logger.setLevel(old_level)


@pytest.fixture
def records():
    """Everything the "shared" logger records, debug included."""
    found = []
    handler = logging.Handler(level=logging.DEBUG)
    handler.emit = found.append
    logger = logging.getLogger("shared")
    logger.addHandler(handler)
    yield found
    logger.removeHandler(handler)


def _menu(monkeypatch, merge_runner):
    """Answer the main menu with Merge Databases, then Quit."""
    answers = ["merge", "quit"]
    asked = []

    def main_prompt():
        asked.append(answers[0])
        return answers.pop(0)

    monkeypatch.setattr(menu.prompts, "main_prompt", main_prompt)
    monkeypatch.setattr(menu.merge, "merge_runner", merge_runner)
    return asked


def _fail(exc):
    def runner():
        raise exc

    return runner


def test_failed_action_is_shown_and_the_menu_comes_back(monkeypatch, screen, records):
    asked = _menu(monkeypatch, _fail(RuntimeError(ERROR_TEXT)))
    assert menu.main_menu_action() is True
    assert asked == ["merge", "quit"]  # the menu came back after the error
    shown = screen.getvalue()
    # names the action and the error, brackets and backslash printed as is
    assert f"Merge Databases failed: RuntimeError: {ERROR_TEXT}" in shown
    # no traceback at the normal level
    assert "Traceback" not in shown
    tracebacks = [r for r in records if "Traceback" in r.getMessage()]
    assert tracebacks and all(r.levelno == logging.DEBUG for r in tracebacks)
    assert "RuntimeError" in tracebacks[0].getMessage()


def test_failing_menu_prompt_is_shown_too(monkeypatch, screen):
    calls = []

    def main_prompt():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("bad [answer]")
        return "quit"

    monkeypatch.setattr(menu.prompts, "main_prompt", main_prompt)
    assert menu.main_menu_action() is True
    assert "Main Menu failed: ValueError: bad [answer]" in screen.getvalue()


def test_successful_action_shows_no_error(monkeypatch, screen, records):
    ran = []
    asked = _menu(monkeypatch, lambda: ran.append(1))
    assert menu.main_menu_action() is True
    assert ran == [1]
    assert asked == ["merge", "quit"]
    assert "failed" not in screen.getvalue()
    assert not [r for r in records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    "exc", [interactive.NoConsoleError("no console"), KeyboardInterrupt(), SystemExit(2)]
)
def test_no_console_interrupt_and_exit_still_end_the_menu(monkeypatch, screen, exc):
    asked = _menu(monkeypatch, _fail(exc))
    with pytest.raises(type(exc)):
        menu.main_menu_action()
    assert asked == ["merge"]
    assert "failed" not in screen.getvalue()
