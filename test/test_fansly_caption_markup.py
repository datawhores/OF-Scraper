from types import SimpleNamespace

import pytest

import ofscraper.utils.settings as settings
from ofscraper.classes.of.base import base, strip_fansly_markup


@pytest.fixture
def site(monkeypatch):
    def apply(name):
        ns = SimpleNamespace(
            text_length=30, text_type="letter", space_replacer=" ", site=name
        )
        monkeypatch.setattr(settings, "get_settings", lambda: ns)

    return apply


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
    b = base()
    caption = "**[s:lg]IMPREGNATE ME - VIRTUAL POV SEX \U0001f4a6[/s]**\n\nBabe"
    assert b.text_trunicate(b.file_cleanup(caption)) == "IMPREGNATE ME _ VIRTUAL POV SE"


def test_file_name_drops_strike_and_link_syntax(site):
    site("fansly")
    assert base().file_cleanup("~~was~~ [here](https://x.com/y)") == "was here"


def test_database_text_is_plain(site):
    site("fansly")
    caption = "**[s:lg]NEW VIDEO \U0001f4a6[/s]**\n\n[c:blue]Out now[/c]"
    assert base().db_cleanup(caption) == "NEW VIDEO \U0001f4a6 Out now"


def test_onlyfans_text_is_unchanged(site):
    site("onlyfans")
    caption = "***my full attention*** [c:blue]x[/c] ~~y~~"
    assert base().db_cleanup(caption) == caption
    assert base().file_cleanup("~~y~~ [c:blue]x[/c]") == "~~y~~ [cblue]x[c]"
