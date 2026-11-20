from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.utils.settings as settings
from ofscraper.classes.of.base import base
from ofscraper.sites.fansly import normalize
from ofscraper.sites.fansly.normalize import strip_fansly_markup


@pytest.fixture
def site(monkeypatch):
    def apply(name):
        ns = SimpleNamespace(
            text_length=30,
            text_type="letter",
            space_replacer=" ",
            site=name,
            force_all=False,
            force_model_unique=False,
        )
        monkeypatch.setattr(settings, "get_settings", lambda: ns)
        monkeypatch.setattr(posts_.data, "get_sanitizeDB", lambda *a, **k: False)

    return apply


def fansly_post(caption):
    """A Fansly post as a scan reads it: through normalize, which removes the codes."""
    response = {"posts": [{"id": "1", "createdAt": 1760000000, "content": caption}]}
    return posts_.Post(normalize.posts(response)[0], 1, "a creator", "timeline")


def text_placeholder(post):
    # what the {text} placeholder is set to (placeholder.add_main_variables)
    return post.text_trunicate(post.file_sanitized_text)


@pytest.mark.parametrize(
    "caption,expected",
    [
        ("[s:lg]Big[/s] and [c:blue]blue[/c]", "Big and blue"),
        ("[C:Sky-Blue]Tag[/C] case", "Tag case"),
        ("**bold** and *italic* and ~~gone~~", "bold and italic and gone"),
        ("See [my site](https://example.com/a) now", "See my site now"),
        ("[c:pink][link](example.com)[/c] text", "link text"),
        # escaped characters are shown as written, not treated as markup
        (r"\*not italic\* and \[s:lg\] and \\", "*not italic* and [s:lg] and \\"),
        # plain brackets, a single "~" and a lone "*" aren't markup
        (
            "Squish [2 pics] [0:24] ~last chance!~ 2 * 3",
            "Squish [2 pics] [0:24] ~last chance!~ 2 * 3",
        ),
    ],
)
def test_strip_fansly_markup(caption, expected):
    assert strip_fansly_markup(caption) == expected


def test_file_name_uses_whole_length_for_the_caption(site):
    site("fansly")
    post = fansly_post("**[s:lg]IMPREGNATE ME - VIRTUAL POV SEX \U0001f4a6[/s]**\n\nBabe")
    assert text_placeholder(post) == "IMPREGNATE ME _ VIRTUAL POV SE"


def test_file_name_drops_strike_and_link_syntax(site):
    site("fansly")
    post = fansly_post("~~was~~ [here](https://x.com/y)")
    assert post.file_sanitized_text == "was here"
    assert text_placeholder(post) == "was here"


@pytest.mark.parametrize(
    "caption,expected",
    [
        # Fansly shows these as written; the codes come off only once, when
        # the post is read, so file names keep them (less the characters a
        # file name can't hold: ":" and "*")
        (r"\~\~50 off\~\~ now", "~~50 off~~ now"),
        (r"\[s:lg\] literal", "[slg] literal"),
        (r"see \[here\](x) ok", "see [here](x) ok"),
        (r"\*sale\* today", "sale today"),
    ],
)
def test_file_name_keeps_escaped_characters(site, caption, expected):
    site("fansly")
    post = fansly_post(caption)
    assert post.file_sanitized_text == expected
    assert text_placeholder(post) == expected


def test_database_text_is_plain(site):
    site("fansly")
    # the codes come off when the post is read (normalize._item_dict);
    # db_cleanup gets the plain caption and doesn't strip it a second time
    post = fansly_post("**[s:lg]NEW VIDEO \U0001f4a6[/s]**\n\n[c:blue]Out now[/c]")
    assert post.db_sanitized_text == "NEW VIDEO \U0001f4a6 Out now"
    assert fansly_post(r"\*sale\* today").db_sanitized_text == "*sale* today"


def test_onlyfans_text_is_unchanged(site):
    site("onlyfans")
    caption = "***my full attention*** [c:blue]x[/c] ~~y~~"
    assert base().db_cleanup(caption) == caption
    assert base().file_cleanup("~~y~~ [c:blue]x[/c]") == "~~y~~ [cblue]x[c]"
    raw = r"\[c:blue\] \*hi\* ~~y~~"
    post = posts_.Post({"id": 3, "text": raw}, 1, "a creator", "timeline")
    assert post.text == raw
    assert post.file_sanitized_text == r"\[cblue\] \hi\ ~~y~~"
