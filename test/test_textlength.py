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
    import ofscraper.classes.of.base as base_module

    # the cut is logged once per run: start each test with a fresh run
    monkeypatch.setattr(base_module, "_cut_logged", set(), raising=False)

    def apply(**kw):
        ns = SimpleNamespace(text_length=0, text_type="letter", space_replacer=" ")
        ns.__dict__.update(kw)
        monkeypatch.setattr(settings, "get_settings", lambda: ns)

    return apply


def test_letter_mode_truncates(fake_settings):
    fake_settings(text_length=5, text_type="letter")
    assert base().text_trunicate("abcdefghij") == "abcde"


@pytest.mark.parametrize(
    "replacer,text,length",
    [("_", "Good_luck", 5), (" ", "Good luck", 5), ("_", "Good__luck", 6), ("_", "Good _luck", 6)],
)
def test_letter_mode_cut_does_not_end_on_a_separator(fake_settings, replacer, text, length):
    fake_settings(text_length=length, text_type="letter", space_replacer=replacer)
    assert base().text_trunicate(text) == "Good"


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


@pytest.mark.parametrize(
    "text_type,text,length,unit",
    [("letter", "abcdefghij", 5, "letters"), ("word", "one two three", 2, "words")],
)
def test_a_cut_logs_the_unit(fake_settings, caplog, text_type, text, length, unit):
    fake_settings(text_length=length, text_type=text_type)
    with caplog.at_level("DEBUG", logger="shared"):
        base().text_trunicate(text)
    assert f"{{text}} cut to {length} {unit} (text_type_default: {text_type})" in caplog.text


def test_the_cut_is_logged_once_per_run(fake_settings, caplog):
    """text_trunicate runs for each placeholder of each media: the line is
    about the setting, so it is said once."""
    fake_settings(text_length=2, text_type="word")
    with caplog.at_level("DEBUG", logger="shared"):
        for text in ("one two three", "four five six", "one two three"):
            base().text_trunicate(text)
    assert caplog.text.count("cut to 2 words") == 1


def test_text_that_fits_logs_no_cut(fake_settings, caplog):
    fake_settings(text_length=50, text_type="letter")
    with caplog.at_level("DEBUG", logger="shared"):
        base().text_trunicate("short")
    assert "cut to" not in caplog.text


def test_a_trailing_separator_alone_is_not_logged_as_a_cut(fake_settings, caplog):
    fake_settings(text_length=50, text_type="letter", space_replacer="_")
    with caplog.at_level("DEBUG", logger="shared"):
        assert base().text_trunicate("Good_") == "Good"
    assert "cut to" not in caplog.text


# A post's media and its text file get the same {text} (#744): real settings,
# a real post and the real placeholder classes.

from naming_helpers import naming  # noqa: F401  (fixture)


@pytest.mark.parametrize(
    "replacer, expected",
    [("-", "one-two-three-four"), ("_", "one_two_three_four"),
     (".", "one.two.three.four"), (" ", "one two three four")],
)
def test_media_and_text_files_cut_the_caption_alike(naming, replacer, expected):
    text, (media,) = naming(
        "{text}.{ext}", "one two three four five six",
        "--text-type", "word", "--textlength", "4", "--space-replacer", replacer,
    )
    assert (text, media) == (f"{expected}.txt", f"{expected}.jpg")


@pytest.mark.parametrize(
    "url, expected",
    [("https://example.invalid/my-pic.jpg", "my_pic"),  # the file name
     (None, "2026_10_31")],  # no file name either: the post's date
)
def test_media_with_no_usable_caption_uses_the_cleaned_file_name_or_date(
    naming, monkeypatch, url, expected
):
    """A caption that cleans to nothing (only HTML here): a media file's
    {text} falls back to its file name, then the date, cleaned once there
    (the "-" becomes "_")."""
    import naming_helpers

    make_post = naming_helpers.make_post

    def post_with_url(caption, media=1):
        post = make_post(caption, media)
        for item in post.all_media:
            item._media["files"]["full"]["url"] = url
        return post

    monkeypatch.setattr(naming_helpers, "make_post", post_with_url)
    _, (media,) = naming(
        "{text}.{ext}", "<br />", "--space-replacer", "-", text=False
    )
    assert media == f"{expected}.jpg"


@pytest.mark.parametrize("caption", ["<p> </p>", "  ", "<br />\n<br />", "???"])
def test_media_with_a_caption_of_only_spaces_uses_the_file_name(
    naming, monkeypatch, caption
):
    """A caption that cleans to nothing, or to nothing but spaces (or the
    space_replacer standing for them), names nothing: {text} falls back to
    the media's file name, not "-" or the post id."""
    import naming_helpers

    make_post = naming_helpers.make_post

    def post_with_url(text, media=1):
        post = make_post(text, media)
        for item in post.all_media:
            item._media["files"]["full"]["url"] = "https://example.invalid/my-pic.jpg"
        return post

    monkeypatch.setattr(naming_helpers, "make_post", post_with_url)
    _, (media,) = naming(
        "{text}.{ext}", caption, "--space-replacer", "-", text=False
    )
    assert media == "my_pic.jpg"


def test_a_profile_image_with_no_text_uses_the_cleaned_date_and_file_name(
    naming, monkeypatch
):
    """A profile image's {text} is its date and its text, or its file name
    when it has none, cleaned once ("-" and ":" go, spaces become the
    space_replacer). A profile image's own name doesn't use file_format, so
    this reads the {text} the placeholders hand on (e.g. to a naming script)."""
    import asyncio

    import naming_helpers
    import ofscraper.classes.placeholder as placeholder

    make_post = naming_helpers.make_post
    built = []

    def profile_post(caption, media=1):
        post = make_post(caption, media)
        profile = naming_helpers.posts_.Post(post.post, 1, "u", "profile")
        for item in profile.all_media:
            item._media["files"]["full"]["url"] = "https://example.invalid/my-pic.jpg"
        built.append(profile)
        return profile

    monkeypatch.setattr(naming_helpers, "make_post", profile_post)
    naming("{text}.{ext}", None, "--space-replacer", "~", text=False)
    names = placeholder.Placeholders(built[0].all_media[0], "jpg")
    asyncio.run(names.createfilename())
    assert names._variables["text"] == "2026_10_31~120000+0000~my_pic_2026_10_31"
