import sys
from types import SimpleNamespace

import pytest
from InquirerPy.base import Choice

import ofscraper.prompts.utils.prompt_helpers as prompt_helpers
from ofscraper.utils.context import stdout


def test_nostdout_restores_stdout_on_exception():
    before = sys.stdout
    with pytest.raises(KeyboardInterrupt):
        with stdout.nostdout():
            raise KeyboardInterrupt
    assert sys.stdout is before


def test_nostdout_hides_and_restores():
    before = sys.stdout
    with stdout.nostdout():
        assert sys.stdout is not before
    assert sys.stdout is before


def _prompt(n, selected):
    choices = [Choice(i, name=f"{i + 1}: m{i}   => details") for i in range(n)]
    return SimpleNamespace(
        content_control=SimpleNamespace(_raw_choices=choices),
        selected_choices=[{"name": choices[i].name} for i in selected],
    )


@pytest.fixture
def no_filter_menu(monkeypatch):
    def boom():
        raise AssertionError("range select must not reopen the filter menu (#29)")

    monkeypatch.setattr(prompt_helpers, "_get_choices", boom)


def _enabled(choices):
    return [c.value for c in choices if c.enabled]


def test_range_select_uses_visible_list(monkeypatch, no_filter_menu):
    monkeypatch.setattr(
        prompt_helpers.promptConvert, "multiline_input_prompt", lambda **k: "2-4,30"
    )
    out = prompt_helpers._select_helper(_prompt(30, selected=[0]), toggle=True)
    assert _enabled(out) == [0, 1, 2, 3, 29]


def test_range_deselect_keeps_the_rest(monkeypatch, no_filter_menu):
    monkeypatch.setattr(
        prompt_helpers.promptConvert, "multiline_input_prompt", lambda **k: "1"
    )
    out = prompt_helpers._select_helper(_prompt(5, selected=[0, 2]), toggle=False)
    assert _enabled(out) == [2]
