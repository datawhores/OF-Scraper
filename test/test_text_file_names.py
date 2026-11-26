"""A post's text file name doesn't repeat the caption (#736)."""

import asyncio

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.settings as settings
from ofscraper.utils.args.main import AutoDotDict
from ofscraper.utils.args.parse.commands.main import program
from test_undated_posts import names_env  # noqa: F401  (fixture)

CAPTION = "Look at this sunset over the bay"


@pytest.fixture
def text_settings(monkeypatch, names_env):  # noqa: F811
    """Real settings with --text-type word, cut to 4 words as textlength 4 would."""
    params, _ = program.main(
        args=["--text-type", "word"], standalone_mode=False, prog_name="OF-Scraper"
    )
    args = AutoDotDict(params)
    args.command = "OF-Scraper"
    monkeypatch.setattr(settings.read_args, "retriveArgs", lambda *a, **k: args)
    merged = settings.merged_settings()
    merged.text_length = 4
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: merged)
    return merged


def text_name(monkeypatch, file_format, caption=CAPTION):
    monkeypatch.setattr(placeholder.data, "get_fileformat", lambda *a, **k: file_format)
    raw = {"id": 8, "text": caption, "price": 0, "isOpened": True,
           "responseType": "post", "postedAt": "2026-10-31T12:00:00+00:00"}
    holder = placeholder.Textholders(posts_.Post(raw, 1, "u", "timeline"), "txt")
    return asyncio.run(holder.createfilename())


@pytest.mark.parametrize("name", ["filename", "file_name", "only_filename",
                                  "only_file_name", "original_filename"])
def test_text_and_filename_together_name_the_caption_once(monkeypatch, text_settings, name):
    out = text_name(monkeypatch, "{date} {%s} {text}.{ext}" % name)
    # {filename} is left out, with the space after it
    assert out == "2026-10-31 Look at this sunset.txt"


@pytest.mark.parametrize("file_format, name", [
    # the separator next to {filename} goes with it, wherever it is
    ("{filename} {text}.{ext}", "Look at this sunset.txt"),
    ("{filename}_{text}.{ext}", "Look at this sunset.txt"),
    ("{text} {filename}.{ext}", "Look at this sunset.txt"),
    ("{text} - {filename}.{ext}", "Look at this sunset.txt"),
    ("{date} - {filename} - {text}.{ext}", "2026-10-31 - Look at this sunset.txt"),
    ("{date}_{filename}_{post_id}_{text}.{ext}", "2026-10-31_8_Look at this sunset.txt"),
    ("{filename}{text}.{ext}", "Look at this sunset.txt"),
])
def test_the_separator_beside_filename_goes_with_it(monkeypatch, text_settings, file_format, name):
    assert text_name(monkeypatch, file_format) == name


def test_a_media_file_keeps_its_filename(monkeypatch, text_settings):
    monkeypatch.setattr(
        placeholder.data, "get_fileformat", lambda *a, **k: "{date} {filename} {text}.{ext}"
    )
    raw = {"id": 8, "text": CAPTION, "price": 0, "isOpened": True,
           "responseType": "post", "postedAt": "2026-10-31T12:00:00+00:00",
           "media": [{"id": 70, "type": "photo", "canView": True,
                      "files": {"full": {"url": "https://example.invalid/pic.jpg"}}}]}
    item = posts_.Post(raw, 1, "u", "timeline").all_media[0]
    out = asyncio.run(placeholder.Placeholders(item, "jpg").createfilename())
    assert out == "2026-10-31 pic Look at this sunset.jpg"


def test_filename_alone_is_still_the_caption(monkeypatch, text_settings):
    assert text_name(monkeypatch, "{date} {filename}.{ext}") == "2026-10-31 Look at this sunset.txt"


def test_text_alone_is_unchanged(monkeypatch, text_settings):
    assert text_name(monkeypatch, "{date} {text}.{ext}") == "2026-10-31 Look at this sunset.txt"


@pytest.mark.parametrize("file_format, name", [
    # other separators: one is kept between the parts that remain
    ("{date}.{filename}.{text}.{ext}", "2026-10-31.Look at this sunset.txt"),
    ("{text} - {filename} ({post_id}).{ext}", "Look at this sunset (8).txt"),
    ("{text}.{filename}.{ext}", "Look at this sunset.txt"),
    # brackets around {filename} go with it
    ("{text} ({filename}).{ext}", "Look at this sunset.txt"),
    ("{text} [{filename}] {post_id}.{ext}", "Look at this sunset 8.txt"),
    # a folder named by {filename} alone is left out with its slash
    ("{filename}/{text}.{ext}", "Look at this sunset.txt"),
    ("{date}/{filename}/{text}.{ext}", "2026-10-31/Look at this sunset.txt"),
])
def test_uncommon_separators_beside_filename_go_with_it(monkeypatch, text_settings, file_format, name):
    assert text_name(monkeypatch, file_format) == name


def test_a_file_named_by_filename_alone_keeps_the_caption(monkeypatch, text_settings):
    # with {filename} left out the file would be named ".txt", a hidden file
    # with no name: the caption stays there
    out = text_name(monkeypatch, "{text}/{filename}.{ext}")
    assert out == "Look at this sunset/Look at this sunset.txt"


@pytest.mark.parametrize("caption, file_format, name", [
    # dots or dashes that belong to the caption aren't taken as separators
    ("Wait for it...", "{text} {filename}.{ext}", "Wait for it....txt"),
    ("...and then", "{filename} {text}.{ext}", "...and then.txt"),
    ("Wait for it...", "{text}.{filename}.{ext}", "Wait for it....txt"),
])
def test_the_captions_own_dots_stay(monkeypatch, text_settings, caption, file_format, name):
    assert text_name(monkeypatch, file_format, caption) == name


@pytest.mark.parametrize("file_format, name", [
    ("/{date} {filename}.{ext}", "/2026-10-31 Look at this sunset.txt"),
    ("{date}//{filename}.{ext}", "2026-10-31//Look at this sunset.txt"),
])
def test_a_name_without_text_is_formatted_as_before(monkeypatch, text_settings, file_format, name):
    assert text_name(monkeypatch, file_format) == name


@pytest.mark.parametrize("file_format, name", [
    ("/{date} {text}.{ext}", "/2026-10-31 Look at this sunset.txt"),
    ("{date}//{text}.{ext}", "2026-10-31//Look at this sunset.txt"),
])
def test_a_name_with_text_but_no_filename_is_formatted_as_before(monkeypatch, text_settings, file_format, name):
    # nothing is left out, so the name is file_format filled in as it was
    assert text_name(monkeypatch, file_format) == name
