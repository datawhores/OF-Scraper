from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.settings as settings
from ofscraper.classes.of.base import base
from ofscraper.utils.args.parse.arguments.file import text_type_option


@pytest.fixture
def fake_settings(monkeypatch):
    def apply(**kw):
        ns = SimpleNamespace(text_length=0, text_type="letter", space_replacer=" ")
        ns.__dict__.update(kw)
        monkeypatch.setattr(settings, "get_settings", lambda: ns)

    return apply


def test_letter_mode_truncates(fake_settings):
    fake_settings(text_length=5, text_type="letter")
    assert base().text_trunicate("abcdefghij") == "abcde"


def test_zero_length_keeps_text(fake_settings):
    fake_settings(text_length=0)
    assert base().text_trunicate("a b c") == "a b c"


@pytest.mark.parametrize("n,expected", [(1, "one"), (2, "one two"), (3, "one two three")])
def test_word_mode_counts_words(fake_settings, n, expected):
    fake_settings(text_length=n, text_type="word")
    assert base().text_trunicate("one two three four") == expected


def test_word_mode_uses_space_replacer(fake_settings):
    fake_settings(text_length=2, text_type="word", space_replacer="_")
    assert base().text_trunicate("one_two_three") == "one_two"


def test_text_type_option_has_no_default():
    # a CLI default would always override text_type_default from config
    @click.command()
    @text_type_option
    def cmd(text_type):
        click.echo(repr(text_type))

    assert CliRunner().invoke(cmd, []).output.strip() == "None"


def test_settings_reads_textlength_arg(monkeypatch):
    args = settings.get_args(copy=True)
    args.textlength = 7
    args.text_type = None
    monkeypatch.setattr(read_args, "retriveArgs", lambda: args)
    monkeypatch.setattr(config_data, "get_textType", lambda *a, **k: "letter")
    merged = settings.merged_settings()
    assert merged.text_length == 7
    assert merged.text_type == "letter"


def test_settings_falls_back_to_config_textlength(monkeypatch):
    args = settings.get_args(copy=True)
    args.textlength = None
    monkeypatch.setattr(read_args, "retriveArgs", lambda: args)
    monkeypatch.setattr(config_data, "get_textlength", lambda *a, **k: 75)
    assert settings.merged_settings().text_length == 75


def test_word_mode_counts_existing_replacer_chars_as_breaks(fake_settings):
    # documented limitation: "_" already in the caption ("snake_case title")
    # can't be told apart from a replaced space once file_cleanup has run
    fake_settings(text_length=2, text_type="word", space_replacer="_")
    assert base().text_trunicate("snake_case_title_here") == "snake_case"
