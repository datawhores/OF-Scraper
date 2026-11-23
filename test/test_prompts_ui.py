"""Prompt keybindings, resize handling, error lines, and styled table cells."""

# ----------------------------------------------------------------------
# From test_help_key.py
# The prompt help opens with Alt+V or Ctrl+V.
#
# Windows Terminal keeps Ctrl+V for paste, so there it never reaches the
# prompt; other terminals (Linux: Ctrl+Shift+V pastes, macOS: Cmd+V) pass it
# on, and on macOS Terminal Alt+V needs "Use Option as Meta". Both keys stay
# bound, and the help text says when Ctrl+V doesn't work.
# ----------------------------------------------------------------------

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.prompts.promptConvert as promptConvert
import ofscraper.prompts.prompt_strings as prompt_strings


class _Prompt:
    def __init__(self):
        self.keys = []

    def register_kb(self, key):
        def register(handler):
            self.keys.append(key)
            return handler

        return register


def test_help_is_bound_to_alt_v_and_ctrl_v():
    prompt = _Prompt()

    promptConvert.register_keys(prompt, None, None, {}, [None])

    assert "alt-v" in prompt.keys
    assert "c-v" in prompt.keys


def test_help_text_says_where_ctrl_v_pastes_instead():
    for name in ("KEY_BOARD", "NUMBER", "SCRAPE_PAID"):
        text = getattr(prompt_strings, name)
        assert "[ALT+V] or [CTRL+V]" in text
        assert "in Windows Terminal, Ctrl+V pastes instead" in text

# ----------------------------------------------------------------------
# From test_live_resize.py
# Resizing starts the shared live display's next frame on a clean screen.
# ----------------------------------------------------------------------

import io

import pytest
from rich.console import Console
from rich.panel import Panel

import ofscraper.main.open.load  # noqa: F401 (import order, see conftest)
import ofscraper.utils.live.live as live_mod


@pytest.mark.parametrize("dimension,smaller", [("width", 40), ("height", 10)])
def test_live_clears_once_per_resize(monkeypatch, dimension, smaller):
    monkeypatch.setenv("TERM", "xterm")
    output = io.StringIO()
    console = Console(
        file=output, force_terminal=True, force_interactive=True, width=80, height=24,
        legacy_windows=False,
    )
    monkeypatch.setattr(live_mod.console_, "get_shared_console", lambda: console)
    monkeypatch.setattr(live_mod, "live", None)
    live = live_mod.get_live()
    live.auto_refresh = False  # Drive refreshes deterministically in this test.
    original = getattr(console, dimension)
    try:
        live_mod.start_live(Panel("first line\nsecond line", title="Activity Progress"))
        live.refresh()
        assert "\x1b[2J" not in output.getvalue()

        for size, clears in [(smaller, 1), (original, 2)]:
            offset = len(output.getvalue())
            setattr(console, dimension, size)
            live.refresh()
            frame = output.getvalue()[offset:]
            assert frame.startswith("\x1b[2J\x1b[H")
            assert "\x1b[1A" not in frame  # No stale cursor-up after clearing.
            assert "Activity Progress" in frame
            assert output.getvalue().count("\x1b[2J") == clears
            live.refresh()
            live.refresh()
            assert output.getvalue().count("\x1b[2J") == clears
    finally:
        live_mod.stop_live()

# ----------------------------------------------------------------------
# From test_prompt_error_line.py
# Validation errors stay above multiline keybinding instructions.
# ----------------------------------------------------------------------

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

# ----------------------------------------------------------------------
# From test_prompt_resize.py
# ----------------------------------------------------------------------

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

# ----------------------------------------------------------------------
# From test_table_styled_other_values.py
# get_styled() shows a cell whose value isn't a str, bool, int or list
# (e.g. None) instead of raising.
# ----------------------------------------------------------------------

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.classes.table.sections.table as table


@pytest.mark.parametrize(
    "canview,want_unlocked,want_cart",
    [(None, False, "Not Unlocked"), (True, True, "[]"), (False, False, "Not Unlocked")],
)
def test_unlocked_cell_agrees_with_cart(canview, want_unlocked, want_cart):
    from types import SimpleNamespace

    import ofscraper.commands.check as check

    ele = SimpleNamespace(canview=canview)
    assert check.unlocked_helper(ele) is want_unlocked
    assert check.checkmarkhelper(ele) == want_cart


@pytest.mark.parametrize("value", [None, 1.5, {"a": 1}])
def test_other_value_types_are_shown(monkeypatch, value):
    monkeypatch.setattr(table, "get_col_names", lambda: ["unlocked", "media_id"])
    row = {"unlocked": value, "media_id": 7}
    cells = table.get_styled(row)
    assert [c.plain for c in cells] == [str(value), "7"]
    assert str(cells[0].style) == "bold white"
