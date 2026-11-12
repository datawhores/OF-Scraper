"""Validation errors stay above multiline keybinding instructions."""

import asyncio
import os
import shutil
from contextlib import nullcontext

import pytest
from InquirerPy.containers.validation import ValidationFloat
from InquirerPy.containers.instruction import InstructionWindow
from prompt_toolkit.application import create_app_session
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

import ofscraper.prompts.promptConvert as prompt_convert


class PromptOutput(DummyOutput):
    columns = 20
    rows = 80

    def get_size(self):
        return Size(rows=self.rows, columns=self.columns)


@pytest.mark.parametrize("rows", [1, 2])
def test_validation_float_with_zero_height_instruction(rows):
    output = PromptOutput()
    output.rows = rows
    with create_app_session(input=DummyInput(), output=output):
        prompt = prompt_convert.inquirer.select(
            message="Choose",
            choices=["One", "Two"],
            long_instruction="First\nSecond\nThird\nFourth",
        )
        prompt_convert.fix_validation_float(prompt)
        container = getattr(prompt._layout, "container", prompt._layout)
        error_float, = (
            float_ for float_ in container.floats
            if isinstance(float_, ValidationFloat)
        )
        help_window, = (
            child.content for child in container.content.get_children()
            if isinstance(child, InstructionWindow)
        )
        bottom = error_float.bottom
        assert help_window.render_info is None

        async def draw():
            with set_app(prompt.application):
                prompt.application.renderer.render(
                    prompt.application, prompt.application.layout
                )

        asyncio.run(draw())
        assert help_window.render_info is None
        assert error_float.bottom == bottom


@pytest.mark.parametrize("prompt_type", ["fuzzy", "list"])
@pytest.mark.parametrize("instruction, rows", [
    ("Short\n\n" + "x" * 21 + "\n" + "y" * 20, 7),
    ("\u754c" * 11, 4),
])
@pytest.mark.parametrize("resize", [False, True])
def test_validation_float_above_multiline_instruction(
    monkeypatch, prompt_type, instruction, rows, resize
):
    monkeypatch.setattr(
        shutil, "get_terminal_size",
        lambda: os.terminal_size((80 if resize else 20, 24)),
    )
    monkeypatch.setattr(prompt_convert.interactive, "require_console", lambda *a: None)
    monkeypatch.setattr(prompt_convert, "prompt_live", nullcontext)
    monkeypatch.setattr(prompt_convert, "clear", lambda: None)
    monkeypatch.setattr(prompt_convert, "get_default", lambda *a: None)
    output = PromptOutput()
    if resize:
        output.columns = 80

    def execute(prompt):
        container = getattr(prompt._layout, "container", prompt._layout)
        error_float, = (
            float_ for float_ in container.floats
            if isinstance(float_, ValidationFloat)
        )
        help_window, = (
            child.content for child in container.content.get_children()
            if isinstance(child, InstructionWindow)
        )
        # Empty more_instruction adds no trailing newline or empty row.
        assert help_window.content.text() == [
            ("class:long_instruction", instruction.upper()
             + "\nESC: GO BACK (NO EFFECT AT TOP LEVEL)")
        ]
        assert help_window.wrap_lines()
        app = prompt.application

        def render():
            async def draw():
                with set_app(app):
                    app.renderer.render(app, app.layout)

            asyncio.run(draw())

        render()
        if resize:
            old_height = help_window.render_info.window_height
            output.columns = 20
            monkeypatch.setattr(app, "_redraw", render)
            app._on_resize()
            assert help_window.render_info.window_height > old_height
        assert help_window.render_info.window_height == rows
        assert error_float.bottom == rows
        return "answer"

    prompt_class = (
        prompt_convert.inquirer.fuzzy
        if prompt_type == "fuzzy"
        else prompt_convert.inquirer.select
    )
    monkeypatch.setattr(prompt_class, "execute", execute)
    with create_app_session(input=DummyInput(), output=output):
        assert prompt_convert.getType(prompt_type)(
            message="Choose",
            choices=["One", "Two"],
            multiselect=True,
            long_instruction=instruction,
            more_instruction="",
        ) == "answer"
