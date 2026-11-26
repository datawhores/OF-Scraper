"""OnlyFans sends label names HTML-escaped: "Nudes &amp; Sexy Videos".

The name was used as sent, so the progress line read "getting posts from
label -> Nudes &amp; Sexy Videos", --label "nudes & sexy videos" matched
nothing, and {label} and the database got "&amp;". get_labels_data now
decodes the name once.
"""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.data.api.labels as labels

RAW = [
    {"id": 1, "name": "Nudes &amp; Sexy Videos"},
    {"id": 2, "name": "26 years old"},
    {"id": 3, "name": "Q&amp;A &lt;3 &quot;best&quot; &#39;s"},
    {"id": 4, "name": None},
]


@pytest.fixture
def api(monkeypatch):
    async def fake_tasks(generators):
        for gen in generators:
            await gen.aclose()
        return [dict(x) for x in RAW]

    monkeypatch.setattr(labels.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(labels, "process_tasks_labels", fake_tasks)


def test_label_names_are_decoded(api):
    out = asyncio.run(labels.get_labels_data(1, c=None))
    assert [x["name"] for x in out] == [
        "Nudes & Sexy Videos",
        "26 years old",
        "Q&A <3 \"best\" 's",
        None,
    ]
    # nothing else about the label changes
    assert [x["id"] for x in out] == [1, 2, 3, 4]


def test_label_filter_matches_the_name_as_written(api, monkeypatch):
    seen = {}

    async def fake_known(labels_, *a, **k):
        seen["labels"] = [x["name"] for x in labels_]
        return {}

    async def fake_posts(labels_, *a, **k):
        return labels_

    monkeypatch.setattr(labels, "get_known_label_posts", fake_known)
    monkeypatch.setattr(labels, "get_posts_for_labels", fake_posts)
    monkeypatch.setattr(labels, "update_check", lambda *a, **k: None)
    monkeypatch.setattr(
        labels.settings,
        "get_settings",
        lambda: SimpleNamespace(label=["nudes & sexy videos"]),
    )

    async def run():
        return await labels.get_labels(1, c=None, username="a_creator")

    asyncio.run(run())
    assert seen["labels"] == ["Nudes & Sexy Videos"]


# --- {label} in folder and file names ---------------------------------------


@pytest.mark.parametrize(
    "name, folder",
    [
        # decoded names can now hold characters Windows won't put in a name
        ("Q&A <3", "Q&A 3"),
        ('"best" <of> 2024?', "best of 2024"),
        ("pics/vids", "picsvids"),  # a slash would add a folder
        ("a:b|c*d\\e", "abcde"),
        # everything else is kept, so existing label folders keep their names
        ("Nudes & Sexy Videos", "Nudes & Sexy Videos"),
        ("26 years old - B-G", "26 years old - B-G"),
        ("it's #1 (new)", "it's #1 (new)"),
        # nothing left: the same "None" as a post without a label
        ("<>", "None"),
        ("None", "None"),
    ],
)
def test_label_placeholder_is_safe_in_a_path(name, folder):
    from ofscraper.classes.placeholder import path_safe_label

    assert path_safe_label(name) == folder


# --- captions in file names ---------------------------------------------------
# A caption reads in a file name as it does on the site (#748): OnlyFans sends
# it HTML-escaped too, and a line break or a <br> separates words.

from naming_helpers import naming  # noqa: F401  (fixture)


@pytest.mark.parametrize(
    "caption, expected",
    [
        ("first line\nsecond line\n\n#tag1 #tag2", "first line second line #tag1 #tag2"),
        ("<p>first line<br />second line</p><p>third</p>", "first line second line third"),
        ("a tab\there, a return\r\nthere", "a tab here, a return there"),
        ("Tom &amp; Jerry don&#039;t", "Tom & Jerry don't"),
        ("non&nbsp;breaking\u00a0space", "non breaking space"),
        # decoded, then what a name can't hold is removed, as for {label}
        ("Q&amp;A &lt;3 &quot;best&quot;", "Q&A 3 best"),
        ("<b>bold</b> and <i>italic</i>", "bold and italic"),
    ],
)
def test_a_caption_reads_in_a_name_as_on_the_site(naming, caption, expected):
    text, (media,) = naming("{text}.{ext}", caption)
    assert (text, media) == (f"{expected}.txt", f"{expected}.jpg")


def test_words_on_separate_lines_count_as_separate_words(naming):
    text, (media,) = naming(
        "{text}.{ext}", "one\ntwo three", "--text-type", "word", "--textlength", "2"
    )
    assert (text, media) == ("one two.txt", "one two.jpg")


def test_a_caption_with_nothing_for_a_name_is_the_post_id(naming):
    # the text file's name; a media file falls back to its own file name,
    # then the date (test_textlength.py)
    text, _ = naming("{text}.{ext}", "???")
    assert text == "8.txt"
    # a text file's {filename} is its caption too
    assert naming("{filename}.{ext}", "???")[0] == "8.txt"


@pytest.mark.parametrize(
    "caption, expected",
    [
        # an encoded line break or tab separates words, as a written one does
        ("first&#10;second", "first second"),
        ("first&#13;&#10;second&#9;third", "first second third"),
        ("first&#x0A;second", "first second"),
    ],
)
def test_an_encoded_line_break_separates_words(naming, caption, expected):
    text, (media,) = naming("{text}.{ext}", caption)
    assert (text, media) == (f"{expected}.txt", f"{expected}.jpg")


@pytest.mark.parametrize(
    "caption, expected",
    [
        # a decoded "\" or "/" would be a folder in the name: "\..\" climbs
        # out of the save folder on Windows
        ("a&#92;..&#92;b", "a..b"),
        ("&#47;etc&#47;passwd", "etcpasswd"),
        ("a&bsol;b&sol;c&#x5C;d", "abcd"),
    ],
)
def test_a_decoded_path_separator_is_removed(naming, caption, expected):
    text, (media,) = naming("{text}.{ext}", caption)
    assert (text, media) == (f"{expected}.txt", f"{expected}.jpg")


@pytest.mark.parametrize(
    "caption",
    # an entity written in the caption ("&amp;" typed) reaches OnlyFans'
    # text escaped once more: decoded once, it's the entity, as typed
    ["Tom &amp;amp; Jerry", "&amp;copy; 2026", "a &amp;lt;3 b", "&amp;#39;x"],
)
def test_a_media_name_and_a_text_name_read_a_caption_the_same(naming, caption):
    # a media file's {text} is cleaned from the post's cleaned caption: a
    # second clean mustn't decode the caption again
    text, (media,) = naming("{text}.{ext}", caption)
    assert text[: -len(".txt")] == media[: -len(".jpg")]
