"""Esc cancels whole menu choices without submitting an answer (#437)."""

from contextlib import nullcontext
from threading import Timer
from time import monotonic
from types import SimpleNamespace

import pytest
from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import ofscraper.main.open.load  # noqa: F401 (import order, see conftest)
import ofscraper.prompts.promptConvert as convert
import ofscraper.utils.menu as menu
import ofscraper.utils.profiles.manage as profiles


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setattr(convert.interactive, "require_console", lambda *a: None)
    monkeypatch.setattr(convert, "prompt_live", nullcontext)
    monkeypatch.setattr(convert, "clear", lambda: None)
    with create_pipe_input() as pipe:
        with create_app_session(input=pipe, output=DummyOutput()):
            yield pipe


def test_escape_delay_preserves_default_binding_timeout(terminal):
    application = Application()
    default_timeoutlen = application.timeoutlen

    convert.escape_delay(application)

    assert application.timeoutlen == default_timeoutlen
    assert application.ttimeoutlen == 0.1


@pytest.mark.parametrize(
    "factory, options",
    [
        ("getChecklistSelection", {"choices": ["one", "two"]}),
        ("getFuzzySelection", {"choices": ["one", "two"], "multiselect": True}),
        ("checkbox", {"choices": ["one", "two"]}),
        ("input_prompt", {"default": "unchanged"}),
        ("multiline_input_prompt", {"default": "unchanged"}),
        ("file_type", {"default": "."}),
        ("number_type", {"default": 2}),
        ("confirm_prompt", {"default": True}),
    ],
)
def test_escape_cancels_every_prompt_promptly(terminal, factory, options):
    # A delayed Enter lets the old implementation finish rather than hang.
    # In particular, the old multiline prompt actually *submitted* on Esc.
    timer = Timer(1.5, terminal.send_text, args=("\r",))
    completed = []
    filtered = []
    terminal.send_text("\x1b")
    timer.start()
    start = monotonic()
    try:
        with getattr(convert, "cancel_scope", nullcontext)():
            getattr(convert, factory)(
                message="A prompt",
                filter=lambda answer: filtered.append(answer) or answer,
                **options,
            )
            completed.append(True)
    finally:
        timer.cancel()
        timer.join()
    assert completed == []
    assert filtered == []
    # Esc can wait for the default binding timeout when an Alt key shares it.
    assert monotonic() - start < 1.5


def test_top_level_escape_does_nothing(terminal):
    terminal.send_text("\x1b")
    timer = Timer(0.4, terminal.send_text, args=("\r",))
    timer.start()
    try:
        assert convert.input_prompt(message="Top level", default="unchanged") == "unchanged"
    finally:
        timer.cancel()
        timer.join()


def test_ctrl_c_still_interrupts(terminal):
    terminal.send_text("\x03")
    with pytest.raises(KeyboardInterrupt):
        with convert.cancel_scope():
            convert.input_prompt(message="A prompt")


@pytest.mark.parametrize("keys, expected", [("\x1b[B\r", "two"), ("\x1bv\r", "one")])
def test_arrow_and_alt_sequences_are_not_cancelled(terminal, keys, expected):
    helpers = []
    terminal.send_text(keys)
    with convert.cancel_scope():
        answer = convert.getChecklistSelection(
            message="A menu", choices=["one", "two"], altv=lambda: helpers.append(True)
        )
        assert answer == expected
    assert helpers == ([True] if "v" in keys else [])


def test_escape_is_in_instructions(terminal, monkeypatch):
    build = convert.inquirer.text
    instructions = []

    def text(*args, **kwargs):
        instructions.append(kwargs["long_instruction"])
        return build(*args, **kwargs)

    monkeypatch.setattr(convert.inquirer, "text", text)
    terminal.send_text("\r")
    convert.input_prompt(message="A prompt")
    assert "ESC: GO BACK" in instructions[0]


@pytest.mark.parametrize("step", ["pick", "rename"])
def test_rename_cancel_returns_to_profile_menu_without_changes(monkeypatch, step):
    from ofscraper.prompts.cancel import PromptCancelled

    seen = []
    main_answers = iter(["profile", "quit"])
    profile_answers = iter(["name", "main"])
    monkeypatch.setattr(menu.prompts, "main_prompt", lambda: next(main_answers))

    def profile_menu():
        seen.append("profile")
        return next(profile_answers)

    def cancel(*args):
        raise PromptCancelled()

    monkeypatch.setattr(menu.prompts, "profiles_prompt", profile_menu)
    monkeypatch.setattr(profiles.tools, "print_profiles", lambda: None)
    monkeypatch.setattr(profiles.profile_data, "get_profiles", lambda: ["main_profile"])
    monkeypatch.setattr(profiles.prompts, "edit_profiles_prompt", cancel if step == "pick" else lambda p: "main_profile")
    monkeypatch.setattr(profiles.prompts, "new_name_edit_profiles_prompt", cancel)
    monkeypatch.setattr(profiles.manager, "Manager", SimpleNamespace(
        profile_manager=SimpleNamespace(rename_profile=lambda *a: pytest.fail("renamed"))
    ))
    assert menu.main_menu_action() is True
    assert seen == ["profile", "profile"]


def test_create_cancel_does_not_create_a_directory(monkeypatch):
    from ofscraper.prompts.cancel import PromptCancelled

    monkeypatch.setattr(profiles.tools, "print_profiles", lambda: None)
    monkeypatch.setattr(profiles.prompts, "create_profiles_prompt", lambda: "new_profile")

    def cancel():
        raise PromptCancelled()

    monkeypatch.setattr(profiles.prompts, "change_selected_profile", cancel)
    monkeypatch.setattr(profiles.manage, "create_profile_path", lambda *a: pytest.fail("created directory"))
    menu.profile_menu_helper("create")


def test_config_cancel_discards_earlier_number_answer(monkeypatch):
    from ofscraper.prompts.cancel import PromptCancelled
    import ofscraper.prompts.prompt_groups.config as config_prompts

    answers = []

    def batch(*args, **kwargs):
        answers.append(args[0]["name"])
        if len(answers) == 1:
            return {"download_sems": 3}
        raise PromptCancelled()

    monkeypatch.setattr(config_prompts.promptClasses, "batchConverter", batch)
    monkeypatch.setattr(config_prompts.data, "get_download_semaphores", lambda: 1)
    monkeypatch.setattr(config_prompts.data, "get_download_limit", lambda: 0)
    monkeypatch.setattr(menu.config_menu, "update_config_helper", lambda *a: pytest.fail("saved config"))
    monkeypatch.setattr(menu.config_menu.config_context, "config_context", nullcontext)
    monkeypatch.setattr(menu.config_menu.config_file, "open_config", lambda: {})
    menu.config_menu_helper("performance")
    assert answers == ["download_sems", "download_limit"]


def test_auth_repair_cancel_does_not_truncate_the_file(monkeypatch):
    from ofscraper.prompts.cancel import PromptCancelled
    import ofscraper.utils.auth.utils.error as error

    original = "{unfinished"
    monkeypatch.setattr("builtins.open", lambda *a, **k: pytest.fail("opened auth for writing"))

    def cancel(*args):
        raise PromptCancelled()

    monkeypatch.setattr(error.prompts, "manual_auth_prompt", cancel)
    with convert.cancel_scope():
        error._manual_auth(original)


def test_range_cancel_keeps_existing_checklist(monkeypatch):
    from InquirerPy.base import Choice
    from ofscraper.prompts.cancel import PromptCancelled
    import ofscraper.prompts.utils.prompt_helpers as helpers

    choices = [Choice("one", "1: one", enabled=True)]
    checklist = SimpleNamespace(
        content_control=SimpleNamespace(_raw_choices=choices),
        selected_choices=[{"name": "1: one"}],
    )

    def cancel(*args, **kwargs):
        raise PromptCancelled()

    monkeypatch.setattr(helpers.promptConvert, "multiline_input_prompt", cancel)
    with convert.cancel_scope():
        helpers._select_helper(checklist)
    assert choices[0].enabled is True


def test_cancellation_rolls_back_run_arguments(monkeypatch):
    from copy import deepcopy
    from ofscraper.prompts.cancel import PromptCancelled
    import ofscraper.utils.settings as settings

    state = {"args": SimpleNamespace(actions=["download"], force_all=False)}
    monkeypatch.setattr(settings, "get_args", lambda copy=False: deepcopy(state["args"]) if copy else state["args"])
    monkeypatch.setattr(settings, "update_args", lambda args: state.update(args=args))
    with convert.cancel_scope(restore_args=True):
        state["args"].force_all = True
        raise PromptCancelled()
    assert state["args"].force_all is False
