from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from InquirerPy.prompts.fuzzy import FuzzyPrompt
from InquirerPy.prompts.input import InputPrompt
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

import ofscraper.prompts.promptConvert as promptConvert


@pytest.mark.parametrize(
    "prompt",
    [
        SimpleNamespace(),
        SimpleNamespace(_session=SimpleNamespace()),
        SimpleNamespace(application=None),
        SimpleNamespace(_session=SimpleNamespace(app=SimpleNamespace())),
        SimpleNamespace(application=SimpleNamespace()),
    ],
)
def test_prompt_resize_without_application_leaves_prompt_alone(prompt):
    before = repr(prompt)

    promptConvert.clear_on_resize(prompt)

    assert repr(prompt) == before


@pytest.mark.parametrize("prompt_type", ["fuzzy", "input"])
def test_prompt_resize_clears_screen_and_redraws(monkeypatch, prompt_type):
    monkeypatch.setattr(promptConvert.interactive, "require_console", lambda *a: None)
    monkeypatch.setattr(promptConvert, "prompt_live", nullcontext)
    monkeypatch.setattr(promptConvert, "clear", lambda: None)
    resized = []

    def execute(prompt):
        app = prompt._session.app if hasattr(prompt, "_session") else prompt.application
        calls = Mock()
        monkeypatch.setattr(app.renderer, "clear", calls.clear)
        monkeypatch.setattr(app.renderer, "erase", calls.erase)
        monkeypatch.setattr(app, "_request_absolute_cursor_position", calls.cursor)
        monkeypatch.setattr(app, "_redraw", calls.redraw)

        app._on_resize()

        assert calls.mock_calls == [call.clear(), call.redraw()]
        resized.append(app)
        return None

    monkeypatch.setattr(FuzzyPrompt, "execute", execute)
    monkeypatch.setattr(InputPrompt, "execute", execute)
    with create_app_session(input=DummyInput(), output=DummyOutput()):
        if prompt_type == "fuzzy":
            promptConvert.getFuzzySelection(message="Select items", choices=["Item"])
        else:
            promptConvert.input_prompt(message="Enter text")

    assert len(resized) == 1
