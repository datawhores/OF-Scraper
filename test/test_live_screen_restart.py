"""stop_live_screen() and the last frame of the live display (#420, #421).

The shared console here writes to a StringIO, so it isn't a terminal: rich
prints the live display only when it stops, and only if it isn't transient.
What lands in the StringIO is the frame that would be left on screen.
"""

import io

import pytest
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, TextColumn

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.console as console
import ofscraper.utils.live.empty as empty
import ofscraper.utils.live.live as live_mod
import ofscraper.utils.live.screens as screens


@pytest.fixture
def shared(monkeypatch):
    """A fresh shared console writing to a StringIO, and a live display on it."""
    monkeypatch.setattr(console, "shared_console", None)
    real = console.get_shared_console()
    real.file = io.StringIO()
    real.width = 60
    monkeypatch.setattr(live_mod, "live", None)
    live_mod.get_live()
    monkeypatch.setattr(empty.time, "sleep", lambda s: None)
    yield real
    live = live_mod.live
    if live is not None and live.is_started:
        live.stop()


def _activity_panel():
    """An "Activity Progress" panel like the menu's, with its own progress."""
    progress = Progress(TextColumn("{task.description}"))
    task = progress.add_task("Getting models", visible=False)
    return progress, task, Group(Panel(progress, title="Activity Progress"))


def _start(layout):
    live = live_mod.get_live()
    live.update(layout)
    live.start()
    return live


def _shown(live):
    """The text the live display draws now."""
    out = Console(file=io.StringIO(), width=60)
    out.print(live.get_renderable())
    return out.file.getvalue()


def _panel(text):
    progress = Progress(TextColumn("{task.description}"))
    progress.add_task(text)
    return Group(Panel(progress))


def _prompt_via_stop_live_screen():
    return screens.stop_live_screen()


def _prompt_via_prompt_live():
    return empty.prompt_live()


@pytest.mark.parametrize(
    "prompt", [_prompt_via_stop_live_screen, _prompt_via_prompt_live]
)
def test_a_prompt_inside_a_screen_then_the_screen_closes(shared, prompt):
    """Closing a screen puts the outer layout back on the running display.

    The prompt replaces the live display with a new one, so the screen has
    to put its layout back on that one, not on the display it opened on.
    """
    _start(_panel("outer layout"))
    with screens.ProgressLayoutManager(layout=_panel("inner layout")):
        with prompt():
            pass
        assert "inner layout" in _shown(live_mod.live)
    assert live_mod.live.is_started
    shown = _shown(live_mod.live)
    assert "outer layout" in shown
    assert "inner layout" not in shown


def test_live_display_runs_again_after_the_screen(shared):
    progress, task, layout = _activity_panel()
    progress.update(task, visible=True)
    _start(layout)
    with screens.stop_live_screen():
        # stopped while the prompt is shown
        assert live_mod.live is None or not live_mod.live.is_started
    assert live_mod.live is not None
    assert live_mod.live.is_started
    # with the same panels
    assert live_mod.live.get_renderable() is layout


def test_nested_screens_restart_the_live_display(shared):
    _, _, layout = _activity_panel()
    _start(layout)
    with screens.stop_live_screen():
        with screens.stop_live_screen():
            pass
    assert live_mod.live.is_started
    assert live_mod.live.get_renderable() is layout


def test_live_display_restarts_after_an_error(shared):
    _, _, layout = _activity_panel()
    _start(layout)
    with pytest.raises(ValueError):
        with screens.stop_live_screen():
            raise ValueError("the prompt failed")
    assert live_mod.live.is_started


def test_a_display_started_inside_is_kept(shared):
    _, _, layout = _activity_panel()
    _start(layout)
    with screens.stop_live_screen():
        inner = live_mod.get_live()
        inner.update("the run's own screen")
        inner.start()
    # the run's display is left running, not replaced
    assert live_mod.live is inner
    assert inner.is_started


def test_no_live_display_running(shared):
    with screens.stop_live_screen():
        pass
    assert not live_mod.get_live().is_started
    assert shared.file.getvalue() == ""


def test_no_empty_panel_before_a_prompt(shared):
    # every task hidden, as clear_tasks_by_name leaves it after a run
    _, _, layout = _activity_panel()
    _start(layout)
    with screens.stop_live_screen():
        assert "Activity Progress" not in shared.file.getvalue()
    assert "Activity Progress" not in shared.file.getvalue()


def test_no_empty_panel_before_a_menu_prompt(shared):
    _, _, layout = _activity_panel()
    _start(layout)
    with empty.prompt_live():
        assert "Activity Progress" not in shared.file.getvalue()


def test_progress_that_shows_something_is_kept(shared):
    progress, task, layout = _activity_panel()
    progress.update(task, visible=True)
    _start(layout)
    with screens.stop_live_screen():
        frame = shared.file.getvalue()
    assert "Activity Progress" in frame
    assert "Getting models" in frame


def test_menu_run_then_prompt_leaves_no_empty_panel(shared):
    """A run from the menu, then the next prompt (the #421 report)."""
    import ofscraper.utils.live.updater as updater

    with empty.prompt_live():  # the main menu prompt
        pass
    with screens.stop_live_screen(clear="all"):  # scraperManager.runner
        with screens.setup_live("main_activity"):
            updater.activity.update_task(description="Scraping", visible=True)
    with empty.prompt_live():  # back at the main menu
        pass
    assert "Activity Progress" not in shared.file.getvalue()
    assert live_mod.live.is_started


@pytest.mark.parametrize(
    "renderable, expected",
    [
        (None, False),
        ("", False),
        ("  ", False),
        ("text", True),
        (Panel(""), False),
        (Group(Panel(Group("")), Panel("")), False),
        (Group(Panel(""), Panel("text")), True),
        (object(), True),
    ],
)
def test_shows_something(renderable, expected):
    assert live_mod.shows_something(renderable) is expected


def test_shows_something_follows_the_tasks():
    progress, task, layout = _activity_panel()
    assert not live_mod.shows_something(layout)
    progress.update(task, visible=True)
    assert live_mod.shows_something(layout)
