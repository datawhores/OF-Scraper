"""Esc in the creator picker keeps the creators that were ticked.

Ticking creators and leaving the picker with Esc threw the ticks away: the
next run's "Do you want to reset username info" -> "No" used the previous
queue (e.g. all 71 creators) instead of the two just ticked. The ticks are
now kept as the selection until a run queues one; with nothing ticked the
previous selection stays.
"""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.managers.model as model
import ofscraper.prompts.prompt_groups.model as model_prompts
import ofscraper.prompts.promptConvert as convert
import ofscraper.utils.settings as settings
from ofscraper.prompts.cancel import PromptCancelled

# --- the prompt: Esc hands the ticked choices to on_cancel ------------------


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setattr(convert.interactive, "require_console", lambda *a: None)
    monkeypatch.setattr(convert, "prompt_live", nullcontext)
    monkeypatch.setattr(convert, "clear", lambda: None)
    with create_pipe_input() as pipe:
        with create_app_session(input=pipe, output=DummyOutput()):
            yield pipe


@pytest.mark.parametrize(
    "keys, expected",
    [
        ("\t\x1b", ["one"]),  # Tab ticks the first and moves down
        ("\t\t\x1b", ["one", "two"]),
        ("\x1b", []),
    ],
    ids=["one ticked", "two ticked", "nothing ticked"],
)
def test_escape_passes_the_ticked_choices_to_on_cancel(terminal, keys, expected):
    seen = []
    terminal.send_text(keys)
    with convert.cancel_scope():
        convert.getFuzzySelection(
            message="Pick",
            choices=["one", "two", "three"],
            multiselect=True,
            on_cancel=lambda prompt: seen.append(model_prompts.ticked_values(prompt)),
        )
        pytest.fail("Esc should have cancelled the prompt")
    assert seen == [expected]


def test_enter_does_not_call_on_cancel(terminal):
    seen = []
    terminal.send_text("\t\r")
    with convert.cancel_scope():
        answer = convert.getFuzzySelection(
            message="Pick",
            choices=["one", "two", "three"],
            multiselect=True,
            on_cancel=seen.append,
        )
    assert answer == ["one"]
    assert seen == []


# --- the model manager: the reset prompt and the picker ---------------------

NAMES = ["creator_a", "creator_b", "creator_c", "creator_d", "creator_e"]
QUEUED = ["creator_c", "creator_d", "creator_e"]  # the previous selection


@pytest.fixture
def manager(monkeypatch):
    mm = model.ModelManager()
    creators = {name: SimpleNamespace(name=name) for name in NAMES}
    mm._all_subs_dict = dict(creators)
    queue = list(QUEUED)
    monkeypatch.setattr(mm, "_get_activities", lambda actions: ["download"])
    monkeypatch.setattr(mm, "_load_all_subs_if_needed", lambda: None)
    monkeypatch.setattr(mm, "_fetch_all_subs", lambda **kwargs: None)
    monkeypatch.setattr(mm, "get_scrape_selected_models", lambda: [creators[n] for n in queue])
    monkeypatch.setattr(mm, "clear_scrape_queues", lambda: queue.clear())
    monkeypatch.setattr(mm.state, "set_queue", lambda act, names: queue.extend(names))
    monkeypatch.setattr(mm, "_filter_and_prompt_for_selection", lambda: creators)
    monkeypatch.setattr(settings, "resetUserSelect", lambda: None)
    real = settings.get_settings
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            **{**vars(real()), "actions": ["download"], "command": None, "usernames": [], "daemon": False}
        ),
    )
    monkeypatch.setattr(model.prompts, "press_enter_to_continue", lambda: None)
    mm.creators = creators
    mm.queue = queue
    return mm


def _answers(monkeypatch, *answers):
    answers = iter(answers)
    monkeypatch.setattr(model.prompts, "reset_username_prompt", lambda: next(answers))


def _picker(monkeypatch, mm, *, ticks=None, pick=None):
    """A picker that records what it opened with, then either leaves with Esc
    after ``ticks`` or returns ``pick``."""
    opened = []

    def picker(choices, existing, on_cancel=None):
        opened.append([m.name for m in existing])
        if pick is not None:
            return [mm.creators[n] for n in pick]
        on_cancel([mm.creators[n] for n in ticks])
        raise PromptCancelled()

    monkeypatch.setattr(model.retriver, "get_selected_model", picker)
    return opened


def _escape_from_picker(monkeypatch, mm, answer, ticks):
    _answers(monkeypatch, answer)
    _picker(monkeypatch, mm, ticks=ticks)
    with pytest.raises(PromptCancelled):
        mm.prepare_scraper_activity()


@pytest.mark.parametrize("answer", ["Selection", "Selection_Strict"])
def test_no_after_escape_uses_the_ticked_creators(monkeypatch, manager, answer):
    # the report: Update Selection, tick two, Esc; next run, answer No
    _escape_from_picker(monkeypatch, manager, answer, ["creator_a", "creator_b"])
    # Esc left the queue as it was
    assert manager.queue == QUEUED

    _answers(monkeypatch, "No")
    opened = _picker(monkeypatch, manager, pick=["creator_c"])
    selection = manager.prepare_scraper_activity()

    assert opened == []  # No doesn't open the picker
    assert [m.name for m in selection] == ["creator_a", "creator_b"]
    assert manager.queue == ["creator_a", "creator_b"]


def test_print_selection_shows_the_ticked_creators(monkeypatch, manager):
    _escape_from_picker(monkeypatch, manager, "Selection", ["creator_a"])
    printed = []
    monkeypatch.setattr(
        model.console, "get_console", lambda: SimpleNamespace(print=printed.append)
    )
    _answers(monkeypatch, None, "No")  # Print Selection, then No
    manager.prepare_scraper_activity()
    assert printed == [["creator_a"]]


def test_picker_reopens_with_the_ticked_creators(monkeypatch, manager):
    _escape_from_picker(monkeypatch, manager, "Selection", ["creator_a", "creator_b"])

    # the picker opened without the reset prompt (e.g. from the filter menu)
    opened = _picker(monkeypatch, manager, pick=["creator_a"])
    manager._select_models_scraper()

    assert opened == [["creator_a", "creator_b"]]


def test_escape_with_nothing_ticked_keeps_the_previous_selection(monkeypatch, manager):
    _escape_from_picker(monkeypatch, manager, "Selection", [])

    _answers(monkeypatch, "No")
    selection = manager.prepare_scraper_activity()

    assert [m.name for m in selection] == QUEUED


def test_ticks_are_forgotten_once_a_selection_is_queued(monkeypatch, manager):
    _escape_from_picker(monkeypatch, manager, "Selection", ["creator_a"])

    # this time the picker is submitted with Enter
    _answers(monkeypatch, "Selection")
    _picker(monkeypatch, manager, pick=["creator_e"])
    manager.prepare_scraper_activity()
    assert manager.queue == ["creator_e"]

    _answers(monkeypatch, "No")
    selection = manager.prepare_scraper_activity()
    assert [m.name for m in selection] == ["creator_e"]
