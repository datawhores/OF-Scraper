"""Fansly style codes are removed from the text that's saved, whatever sanitize_text says."""

import asyncio
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
    # textwrap joins the lines
    assert written_text(monkeypatch, tmp_path, fansly_post()) == PLAIN.replace("\n", " ")


def test_onlyfans_text_is_unchanged(site, monkeypatch, tmp_path):
    site("onlyfans")
    raw = "<p>Hello <b>there</b></p> **[c:blue]as sent[/c]**"
    post = posts_.Post({"id": 3, "text": raw}, 1, "a creator", "timeline")
    assert post.db_text == raw
    assert written_text(monkeypatch, tmp_path, post) == raw


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
