"""A config.json that is valid JSON but doesn't hold a settings object.

A top-level list, string, number or null, or an older {"config": ...} file
whose "config" isn't an object, crashed with AttributeError when the getters
read it. It now goes through the same prompt as a file with a syntax error:
reset to the defaults, edit it, or fix it in an editor and check again.
"""

import json

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.config.utils.context as context
import ofscraper.utils.interactive as interactive
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths

NOT_AN_OBJECT = [
    "[1, 2]",
    "[]",
    '"text"',
    "5",
    "null",
    "true",
    '{"config": [1]}',
    '{"config": "text"}',
    '{"config": 5}',
    '{"config": true}',
]
INVALID_JSON = "{not json"


class _AskedAgain(BaseException):
    """Escapes the `except Exception` retry loop so a regression can't hang."""


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr(config_, "config", None)  # read_config's cache
    with of_env.builtin_defaults():
        yield


@pytest.fixture
def config_path(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(common_paths, "get_config_path", lambda: path)
    return path


def _answers(monkeypatch, *answers):
    """The reset prompt gives these answers, then fails the test if asked again."""
    asked = []
    it = iter(answers)

    def ask():
        asked.append(1)
        try:
            answer = next(it)
        except StopIteration:
            raise _AskedAgain from None
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(context.prompts, "reset_config_prompt", ask)
    return asked


@pytest.mark.parametrize("text", [*NOT_AN_OBJECT, INVALID_JSON])
def test_without_a_console_it_stops_like_a_syntax_error(monkeypatch, config_path, text):
    config_path.write_text(text, encoding="utf-8")
    asked = _answers(monkeypatch, interactive.NoConsoleError("no console"))
    with pytest.raises(interactive.NoConsoleError):
        config_.read_config()
    assert asked == [1]
    assert config_path.read_text(encoding="utf-8") == text  # left as it was


@pytest.mark.parametrize("text", [*NOT_AN_OBJECT, INVALID_JSON])
def test_a_getter_asks_instead_of_crashing(monkeypatch, config_path, text):
    import ofscraper.utils.config.data as data

    config_path.write_text(text, encoding="utf-8")
    _answers(monkeypatch, interactive.NoConsoleError("no console"))
    with pytest.raises(interactive.NoConsoleError):
        data.get_discord()


@pytest.mark.parametrize("text", [*NOT_AN_OBJECT, INVALID_JSON])
def test_reset_writes_the_defaults_like_a_syntax_error(monkeypatch, config_path, text):
    config_path.write_text(text, encoding="utf-8")
    asked = _answers(monkeypatch, "reset")
    config = config_.read_config()
    assert asked == [1]
    assert config == schema.get_current_config_schema(config=False)
    assert json.loads(config_path.read_text(encoding="utf-8")) == config


@pytest.mark.parametrize("text", NOT_AN_OBJECT)
def test_fixed_in_an_editor_is_read_again(monkeypatch, config_path, text):
    config_path.write_text(text, encoding="utf-8")
    fixed = schema.get_current_config_schema(config=False)
    fixed["discord"] = "https://example.invalid/hook"

    asked = []

    def fix_then_again():
        if asked:
            raise _AskedAgain
        asked.append(1)
        config_path.write_text(json.dumps(fixed), encoding="utf-8")
        return "again"

    monkeypatch.setattr(context.prompts, "reset_config_prompt", fix_then_again)
    assert config_.read_config()["discord"] == "https://example.invalid/hook"
    assert asked == [1]


def test_manual_edit_that_still_isnt_an_object_is_asked_again(monkeypatch, config_path):
    config_path.write_text("[1]", encoding="utf-8")
    _answers(monkeypatch, "manual", "manual")
    edits = iter(["[2]", '{"config": {"discord": "x"}}'])
    monkeypatch.setattr(context.prompts, "manual_config_prompt", lambda text: next(edits))
    config_file.open_config()
    # the list was never written; the second edit was, unwrapped
    assert json.loads(config_path.read_text(encoding="utf-8")) == {"discord": "x"}


@pytest.mark.parametrize("wrapped", ["null", "false", '""', "0", "{}"])
def test_an_empty_config_key_is_still_ignored(config_path, wrapped):
    config_path.write_text(f'{{"config": {wrapped}, "discord": "x"}}', encoding="utf-8")
    assert config_file.open_config()["discord"] == "x"


def test_the_wrapped_form_is_still_read(config_path):
    config_path.write_text('{"config": {"discord": "x"}}', encoding="utf-8")
    assert config_file.open_config() == {"discord": "x"}


@pytest.mark.parametrize("value", [[1], "text", 5, None, {"config": [1]}])
def test_write_config_refuses_a_non_object(config_path, value):
    config_path.write_text('{"discord": "kept"}', encoding="utf-8")
    with pytest.raises(ValueError):
        config_file.write_config(json.dumps(value))
    assert config_path.read_text(encoding="utf-8") == '{"discord": "kept"}'
