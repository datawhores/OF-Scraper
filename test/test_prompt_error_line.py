"""Validation errors stay above multiline keybinding instructions."""

import os
import shutil
from contextlib import nullcontext

import pytest
from InquirerPy.containers.validation import ValidationFloat
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

import ofscraper.prompts.promptConvert as prompt_convert


@pytest.mark.parametrize("prompt_type", ["fuzzy", "list"])
def test_validation_float_above_multiline_instruction(monkeypatch, prompt_type):
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((20, 24)))
    monkeypatch.setattr(prompt_convert.interactive, "require_console", lambda *a: None)
    monkeypatch.setattr(prompt_convert, "prompt_live", nullcontext)
    monkeypatch.setattr(prompt_convert, "clear", lambda: None)
    monkeypatch.setattr(prompt_convert, "get_default", lambda *a: None)

    def execute(prompt):
        container = getattr(prompt._layout, "container", prompt._layout)
        error_float, = (
            float_ for float_ in container.floats
            if isinstance(float_, ValidationFloat)
        )
        # The wrapper may add its own help lines around ours, so count the
        # help the prompt actually got: our lines take one short row, one
        # blank row, two wrapped rows and one exact-width row.
        rows = [max(1, -(-len(line) // 20)) for line in prompt._long_instruction.split("\n")]
        assert sum(rows) >= 5
        assert error_float.bottom == sum(rows)
        return "answer"

    prompt_class = (
        prompt_convert.inquirer.fuzzy
        if prompt_type == "fuzzy"
        else prompt_convert.inquirer.select
    )
    monkeypatch.setattr(prompt_class, "execute", execute)
    with create_app_session(input=DummyInput(), output=DummyOutput()):
        assert prompt_convert.getType(prompt_type)(
            message="Choose",
            choices=["One", "Two"],
            multiselect=True,
            long_instruction="Short\n\n" + "x" * 21 + "\n" + "y" * 20,
        ) == "answer"
