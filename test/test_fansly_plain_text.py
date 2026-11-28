"""Fansly style codes are removed from the text that's saved, whatever sanitize_text says."""

import asyncio
import logging
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.commands.stash_sync as stash_sync
import ofscraper.utils.settings as settings
import ofscraper.utils.text as text
from ofscraper.sites.fansly import normalize

CAPTION = (
    "[s:lg]Morning set[/s] **out now**\n"
    "*more* soon ~~maybe~~ [see here](https://example.com/a) #sunday"
)
PLAIN = "Morning set out now\nmore soon maybe see here #sunday"


@pytest.fixture
def site(monkeypatch):
    def apply(name):
        ns = SimpleNamespace(
            site=name,
            force_all=False,
            force_model_unique=False,
            text_length=0,
            text_type="letter",
            space_replacer=" ",
        )
        monkeypatch.setattr(settings, "get_settings", lambda: ns)
        # the default: sanitize_text off
        monkeypatch.setattr(posts_.data, "get_sanitizeDB", lambda *a, **k: False)

    return apply


def fansly_post():
    response = {"posts": [{"id": "1", "createdAt": 1760000000, "content": CAPTION}]}
    return posts_.Post(normalize.posts(response)[0], 1, "a creator", "timeline")


def written_text(monkeypatch, tmp_path, post):
    path = tmp_path / "caption.txt"

    class _Holder:
        def __init__(self, ele, ext):
            self.filepath = path

        async def init(self):
            return self

        def templates(self):
            return path.parent, "", "{text}.{ext}"

    async def _no_script(path):
        pass

    monkeypatch.setattr(text.placeholder, "Textholders", _Holder)
    monkeypatch.setattr(text, "after_download_script", _no_script)
    asyncio.run(text.get_text_process("a creator", post))
    return path.read_text(encoding="utf-8")


def test_fansly_post_text_is_plain():
    post = normalize.posts(
        {"posts": [{"id": "1", "createdAt": 1760000000, "content": CAPTION}]}
    )[0]
    assert post["text"] == PLAIN
    assert post["hashtags"] == ["sunday"]


def test_fansly_message_text_is_plain():
    response = {
        "messages": [
            {"id": "2", "senderId": "1", "createdAt": 1760000000, "content": CAPTION}
        ]
    }
    assert normalize.messages(response)[0]["text"] == PLAIN


def test_fansly_database_text_is_plain_with_sanitize_text_off(site):
    site("fansly")
    assert fansly_post().db_text == PLAIN


def test_fansly_text_file_is_plain(site, monkeypatch, tmp_path):
    site("fansly")
    # with the caption's own lines (#751)
    assert written_text(monkeypatch, tmp_path, fansly_post()) == PLAIN


def test_onlyfans_text_is_unchanged(site, monkeypatch, tmp_path):
    site("onlyfans")
    raw = "<p>Hello <b>there</b></p> **[c:blue]as sent[/c]**"
    post = posts_.Post({"id": 3, "text": raw}, 1, "a creator", "timeline")
    assert post.db_text == raw
    # the text file loses the HTML (#751), and nothing else: these aren't
    # Fansly's codes on OnlyFans
    assert written_text(monkeypatch, tmp_path, post) == (
        "Hello there\n**[c:blue]as sent[/c]**"
    )


def test_stash_sync_keeps_escaped_characters(site):
    # the saved row is plain already; Stash gets it as Fansly shows it
    site("fansly")
    response = {
        "posts": [{"id": "1", "createdAt": 1760000000, "content": r"\*sale\* today"}]
    }
    post = posts_.Post(normalize.posts(response)[0], 1, "a creator", "timeline")
    meta = stash_sync.fansly_post_meta(
        "1", "2025-10-09", {"1": ("posts", post.db_text)}, "a creator"
    )
    assert meta["details"] == "*sale* today"
    assert meta["title"] == "*sale* today"


# A text file reads as the caption does on the site (#751): no HTML, and the
# caption's own lines. Real settings, a real post, the real placeholder classes.

import ofscraper.classes.placeholder as placeholder
from naming_helpers import make_post, naming, text_files  # noqa: F401  (fixture)


def _write_text(naming, monkeypatch, caption, *options, collision="media_id", before=None):
    """Write post 8's text file (named caption.txt). `before` is what a
    file already at that name holds, or a dict of file names and what each
    holds."""

    async def no_script(path):
        pass

    naming("caption.{ext}", "x", *options)
    monkeypatch.setattr(text, "after_download_script", no_script)
    monkeypatch.setattr(
        text.config_data, "get_filename_collision", lambda *a, **k: collision
    )
    post = make_post(caption, 0)
    if before is not None:
        if isinstance(before, str):
            before = {"caption.txt": before}
        folder = asyncio.run(placeholder.Textholders(post, "txt").getmediadir())
        for name, content in before.items():
            (folder / name).write_text(content, encoding="utf-8")
    asyncio.run(text.get_text("u", [post]))


@pytest.mark.parametrize(
    "caption, written",
    [
        ("<p>Line one<br />Line two</p><p>Tom &amp; Jerry</p>",
         "Line one\nLine two\nTom & Jerry"),
        ("New set out now\n\n#tag1 #tag2", "New set out now\n\n#tag1 #tag2"),
        # each of the caption's lines is wrapped on its own
        (" ".join(["word"] * 16) + "\nlast line",
         " ".join(["word"] * 14) + "\nword word\nlast line"),
    ],
)
def test_a_text_file_reads_as_the_caption_does(
    naming, monkeypatch, tmp_path, caption, written
):
    _write_text(naming, monkeypatch, caption)
    assert text_files(tmp_path) == {"caption.txt": written}


def test_a_fansly_caption_in_a_text_file_is_plain_already(naming, monkeypatch, tmp_path):
    # nothing to decode or remove: "<3 ... >" isn't a tag there
    caption = "I <3 you > me &amp; more"
    _write_text(naming, monkeypatch, caption, "--site", "fansly")
    assert list(text_files(tmp_path).values()) == [caption]


OLD_FORM = "<p>Line one<br />Line two</p> <p>Tom &amp; Jerry</p>"


@pytest.mark.parametrize("collision", ["media_id", "overwrite"])
def test_an_older_version_s_text_file_is_corrected_in_place(
    naming, monkeypatch, tmp_path, collision
):
    # written by a version that kept the HTML: the same post's file, so it's
    # rewritten where it is, not left beside a caption_<post_id>.txt
    _write_text(
        naming, monkeypatch, "<p>Line one<br />Line two</p>\n<p>Tom &amp; Jerry</p>",
        collision=collision, before=OLD_FORM,
    )
    assert text_files(tmp_path) == {"caption.txt": "Line one\nLine two\n\nTom & Jerry"}


@pytest.mark.parametrize("taken", [
    {"caption.txt": "another post"},
    {"caption.txt": "another post", "caption_8.txt": "a third post"},
])
def test_an_older_version_s_text_file_at_a_fallback_name_is_corrected_in_place(
    naming, monkeypatch, tmp_path, taken
):
    # the names before it hold other posts' text, which is kept; the post's
    # own file, as an older version wrote it, is rewritten where it is
    own = "caption_8.txt" if len(taken) == 1 else "caption_8_2.txt"
    _write_text(
        naming, monkeypatch, "<p>Line one<br />Line two</p>\n<p>Tom &amp; Jerry</p>",
        before={**taken, own: OLD_FORM},
    )
    assert text_files(tmp_path) == {**taken, own: "Line one\nLine two\n\nTom & Jerry"}


@pytest.mark.parametrize("caption", ["<p></p>", "<br />", "<p> </p><br>"])
def test_a_caption_of_only_markup_writes_no_text_file(
    naming, monkeypatch, tmp_path, caption, caplog
):
    # treated as a post with no caption: no empty file, and nothing for the
    # run's text totals to count
    _write_text(naming, monkeypatch, caption)
    assert text_files(tmp_path) == {}
    post = make_post(caption, 0)
    with caplog.at_level(logging.DEBUG, logger="shared"):
        asyncio.run(text.get_text("u", [post]))
    assert post.text_status is None
    assert "post 8: no text file written, the post has no caption" in caplog.text
    assert text_files(tmp_path) == {}


def test_the_end_of_a_block_is_a_line_break(naming, monkeypatch, tmp_path):
    # as </p> is, and as file names treat these tags (#748)
    _write_text(
        naming, monkeypatch,
        "<div>a</div><div>b</div><ul><li>c</li><li>d</li></ul><h2>e</h2>f",
    )
    assert text_files(tmp_path) == {"caption.txt": "a\nb\nc\nd\ne\nf"}


@pytest.mark.parametrize("caption, written", [
    # the start of a block ends the line before it, as its end does (#748)
    ("Intro<p>Body</p>", "Intro\nBody"),
    ("Intro<div>Body</div>more", "Intro\nBody\nmore"),
    ("<b>Sale</b><ul><li>one</li><li>two</li></ul>", "Sale\none\ntwo"),
    # a block that starts a line adds no empty line
    ("<p>a</p><p>b</p>", "a\nb"),
    ("<p>a</p>\n<p>b</p>", "a\n\nb"),
])
def test_the_start_of_a_block_is_a_line_break(naming, monkeypatch, tmp_path, caption, written):
    _write_text(naming, monkeypatch, caption)
    assert text_files(tmp_path) == {"caption.txt": written}
