"""Ctrl+D and the arrow keys in the fuzzy and checkbox prompts.

Two InquirerPy 0.3.4 bugs that promptConvert.fix_list_keys works around:
"toggle all false" (Ctrl+D) inverted the selection, and Down on a fuzzy
filter that matched nothing raised "integer modulo by zero".
"""

import pytest
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.prompts.keybindings as keybindings
from ofscraper.prompts.promptConvert import fix_list_keys

CHOICES = [Choice("a", "alpha", enabled=True), Choice("b", "beta"), Choice("c", "gamma")]


@pytest.fixture
def session():
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        yield


def _fuzzy():
    prompt = inquirer.fuzzy(
        message="pick",
        choices=[Choice(c.value, c.name, c.enabled) for c in CHOICES],
        multiselect=True,
        keybindings=keybindings.fuzzy,
    )
    fix_list_keys(prompt)
    return prompt


def _checkbox():
    prompt = inquirer.checkbox(
        message="pick",
        choices=[Choice(c.value, c.name, c.enabled) for c in CHOICES],
        keybindings=keybindings.fuzzy,
    )
    fix_list_keys(prompt)
    return prompt


def _press(prompt, action):
    for method in prompt.kb_func_lookup[action]:
        method["func"](None, *method.get("args", []))


def _enabled(prompt):
    return [c["enabled"] for c in prompt.content_control.choices]


@pytest.mark.parametrize("make", [_fuzzy, _checkbox], ids=["fuzzy", "checkbox"])
def test_toggle_all_false_clears_every_choice(session, make):
    prompt = make()
    assert _enabled(prompt) == [True, False, False]

    _press(prompt, "toggle-all-false")
    assert _enabled(prompt) == [False, False, False]

    _press(prompt, "toggle-all-false")  # pressing it again keeps them cleared
    assert _enabled(prompt) == [False, False, False]


@pytest.mark.parametrize("make", [_fuzzy, _checkbox], ids=["fuzzy", "checkbox"])
def test_toggle_all_true_selects_every_choice(session, make):
    prompt = make()

    _press(prompt, "toggle-all-true")
    _press(prompt, "toggle-all-true")

    assert _enabled(prompt) == [True, True, True]


def test_toggle_all_false_leaves_choices_the_filter_hides(session):
    prompt = _fuzzy()
    control = prompt.content_control
    control._filtered_choices = [c for c in control._filtered_choices if c["index"] == 1]
    _press(prompt, "toggle-all-true")
    control._filtered_choices = [c for c in control.choices if c["index"] != 1]

    _press(prompt, "toggle-all-false")

    assert _enabled(prompt) == [False, True, False]


@pytest.mark.parametrize("action", ["down", "up", "toggle", "toggle-down", "toggle-up"])
def test_keys_do_nothing_when_the_filter_matches_nothing(session, action):
    prompt = _fuzzy()
    prompt.content_control._filtered_choices = []
    assert prompt.content_control.choice_count == 0

    _press(prompt, action)  # raised ZeroDivisionError / IndexError before

    assert _enabled(prompt) == [True, False, False]


def test_down_still_moves_with_visible_choices(session):
    prompt = _fuzzy()
    start = prompt.content_control.selected_choice_index

    _press(prompt, "down")

    assert prompt.content_control.selected_choice_index == start + 1
