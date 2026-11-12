"""Prompts and the main menu with the real shared console and live display.

rich 14.1 made live displays nestable: the console keeps a stack of them, and
``Console.clear_live()`` pops that stack (on rich 13.7 it set the console's one
live display to None). Live.stop() already calls it, so ofscraper calling it
again before every prompt and at the top of every main-menu loop popped an
empty stack, and every interactive prompt raised
``IndexError: pop from empty list``.
"""

import io
from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.prompts.promptConvert as promptConvert
import ofscraper.utils.console as console
import ofscraper.utils.live.empty as empty
import ofscraper.utils.live.live as live_mod
import ofscraper.utils.menu as menu
from ofscraper.utils.live.clear import clear


@pytest.fixture
def shared(monkeypatch):
    """A fresh real shared console, and the app's live display on it."""
    monkeypatch.setattr(console, "shared_console", None)
    real = console.get_shared_console()
    real.file = io.StringIO()
    monkeypatch.setattr(live_mod, "live", None)
    live_mod.get_live()  # made on the console above
    monkeypatch.setattr(empty.time, "sleep", lambda s: None)
    yield real
    # don't leave a refresh thread running
    live = live_mod.live
    if live is not None and live.is_started:
        live.stop()


def test_clear_without_a_live_display(shared):
    assert not live_mod.get_live().is_started
    clear()
    clear()
    assert shared.file.getvalue() == "\n\n\n\n"


def test_prompt_while_the_live_display_runs(shared):
    live_mod.start_live()
    with empty.prompt_live():
        # the live display is stopped while the prompt is shown
        assert live_mod.live is None or not live_mod.live.is_started
        clear()  # what promptConvert.wrapper does before showing the prompt
    # and comes back afterwards
    assert live_mod.get_live().is_started
    live_mod.stop_live()
    # and the next one starts and stops cleanly too
    live_mod.get_live().start()
    live_mod.stop_live()


def test_nested_prompts_while_the_live_display_runs(shared):
    live_mod.start_live()
    with empty.prompt_live():
        with empty.prompt_live():
            clear()
        # the inner prompt started the live display again; the outer prompt
        # shows its next question while it runs
        assert live_mod.get_live().is_started
        clear()
    assert live_mod.get_live().is_started
    live_mod.stop_live()


class _Prompt:
    """An InquirerPy prompt that answers at once."""

    _session = SimpleNamespace(message="", default_buffer=SimpleNamespace(text=""))

    def register_kb(self, *keys):
        return lambda handler: handler

    def execute(self):
        return "answer"


@pytest.mark.parametrize("live_running", [False, True])
def test_prompt_wrapper(shared, monkeypatch, live_running):
    monkeypatch.setattr(promptConvert.interactive, "is_interactive", lambda: True)
    if live_running:
        live_mod.start_live()
    ask = promptConvert.wrapper(lambda *a, **k: _Prompt())
    assert ask(message="Question") == "answer"
    assert ask(message="Again") == "answer"
    # prompt_live starts the live display again after the prompt
    assert live_mod.get_live().is_started
    live_mod.stop_live()


@pytest.mark.parametrize("live_running", [False, True])
def test_main_menu_loop_start(shared, monkeypatch, live_running):
    # a scrape run from the menu leaves the live display running
    if live_running:
        live_mod.start_live()
    answers = ["merge", "quit"]
    monkeypatch.setattr(menu.prompts, "main_prompt", lambda: answers.pop(0))
    monkeypatch.setattr(menu.merge, "merge_runner", lambda: None)
    assert menu.main_menu_action() is True
    assert answers == []
