"""The creator picker's search box looks for the typed text in usernames.

It was a fuzzy match over the whole row: the letters could be anywhere, in
order, so "mee" matched an "m" in a name plus the "e"s of "subscribed date"
and listed nearly everyone. The typed text now has to appear as typed, in the
username.
"""

import asyncio
from types import SimpleNamespace

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.prompts.prompt_groups.model as model_prompts
import ofscraper.prompts.promptConvert as promptConvert

ROWS = [
    " 1: meefirst     =>  subscribed date: 2024-01-01 | current_price: 10",
    " 2: jamesecond   =>  subscribed date: 2024-01-02 | current_price: 0",
    " 3: third.melody =>  subscribed date: 2024-01-03 | current_price: 5",
    "10: nomatch      =>  subscribed date: 2024-01-04 | current_price: 3",
]


def _names(rows):
    return [row.split(": ", 1)[1].split()[0] for row in rows]


def _search(text):
    scored = [(model_prompts.username_scorer(text, row), row) for row in ROWS]
    hits = [(score, row) for (score, indices), row in scored if indices is not None]
    hits.sort(key=lambda hit: hit[0], reverse=True)
    return _names(row for _, row in hits)


@pytest.mark.parametrize(
    "text, shown",
    [
        ("me", ["meefirst", "jamesecond", "third.melody"]),
        ("mee", ["meefirst"]),  # not jamesecond: its letters aren't together
        ("MEE", ["meefirst"]),
        (" mee ", ["meefirst"]),
        ("sub", []),  # the rest of the row isn't searched
        ("2024", []),
        ("10", []),  # nor the row number
        ("", ["meefirst", "jamesecond", "third.melody", "nomatch"]),
    ],
)
def test_search_matches_the_typed_text_in_the_username(text, shown):
    assert _search(text) == shown


def test_matched_letters_are_the_ones_highlighted():
    row = ROWS[1]
    score, indices = model_prompts.username_scorer("me", row)

    assert "".join(row[i] for i in indices) == "me"
    assert indices[0] == row.index("jamesecond") + 2


def test_the_picker_uses_the_username_search(monkeypatch):
    seen = {}

    def fuzzy(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(model_prompts.promptClasses, "getFuzzySelection", fuzzy)
    monkeypatch.setattr(
        model_prompts.modelHelpers, "model_selector_choices", lambda models: []
    )

    model_prompts.model_selector([], [])

    assert seen["scorer"] is model_prompts.username_scorer


def test_fuzzy_prompt_filters_with_the_given_scorer():
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        prompt = promptConvert.getFuzzySelection.__wrapped__(
            message="pick",
            choices=list(ROWS),
            multiselect=True,
            scorer=model_prompts.username_scorer,
        )
        control = prompt.content_control
        control._current_text = lambda: "mee"

        shown = asyncio.run(control._filter_choices(0))

    assert _names(choice["name"] for choice in shown) == ["meefirst"]
