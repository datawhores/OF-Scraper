"""Pin today's output for file and folder name rules across every caller:
captions, labels, usernames, dates, dots-only names, Windows reserved device
names, emoji, NFD Unicode, and platform length limits (#856)."""

import pathlib
from types import SimpleNamespace
import unicodedata

import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.sites as sites
import ofscraper.sites.fansly.live as fansly_live
import ofscraper.utils.config.naming_check as naming_check
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.settings as settings
from ofscraper.classes.of.base import base


@pytest.fixture
def clean_settings(monkeypatch):
    def apply(space_replacer=" ", is_fansly=False):
        monkeypatch.setattr(
            settings,
            "get_settings",
            lambda: SimpleNamespace(space_replacer=space_replacer),
        )
        monkeypatch.setattr(sites, "is_fansly", lambda: is_fansly)

    apply()
    return apply


# ----------------------------------------------------------------------
# Captions (base.file_cleanup)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("<p>Hello<br/>world</p>", "Hello world"),
        ("Tom &amp; Jerry &lt;3", "Tom & Jerry 3"),
        ("a&#92;..&#92;b / c:d*e?f\"g|h;i", "a..b cdefghi"),
        ("line1\nline2\tline3\xa0end", "line1 line2 line3 end"),
        ("del\x7fchar\x00null\x1fctrl", "delcharnullctrl"),
        ("dash--to---under", "dash_to_under"),
        ("  spaced   out  ", "spaced out"),
        ("emoji 🔥✨ test", "emoji 🔥✨ test"),
        (unicodedata.normalize("NFD", "café ǖ"), unicodedata.normalize("NFD", "café ǖ")),
    ],
)
def test_caption_cleanup_onlyfans(clean_settings, raw, expected):
    assert base().file_cleanup(raw) == expected


def test_caption_cleanup_space_replacer_and_fansly(clean_settings):
    clean_settings(space_replacer="_", is_fansly=True)
    # Fansly captions are plain text: "<3" is not stripped as an HTML tag,
    # "&amp;" is not HTML-decoded, and forbidden characters ("<", ";") are removed.
    assert base().file_cleanup("<3 you &amp; me") == "3_you_&amp_me"


# ----------------------------------------------------------------------
# Labels (placeholder.path_safe_label)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Q&A <3", "Q&A 3"),
        ("a/b\\c:d*e?f\"g|h", "abcdefgh"),
        ("  spaces - and dashes  ", "spaces - and dashes"),
        ("   <>:*?   ", "None"),
        ("", "None"),
        ("emoji 🔥", "emoji 🔥"),
        (unicodedata.normalize("NFD", "café"), unicodedata.normalize("NFD", "café")),
        # Drift pinned before fixing in a separate change (#856):
        ("a\x7fb", "a\x7fb"),
    ],
)
def test_label_cleanup(label, expected):
    assert placeholder.path_safe_label(label) == expected


# ----------------------------------------------------------------------
# Usernames (fansly_live.folder_name)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "username,expected",
    [
        ("alice", "alice"),
        ("  .alice.  ", "alice"),
        ("a/b\\c", "abc"),
        ("my-creator", "my_creator"),
        ("...", "unknown"),
        ("  . .  ", "unknown"),
        ("🔥creator", "🔥creator"),
        (unicodedata.normalize("NFD", "café"), unicodedata.normalize("NFD", "café")),
    ],
)
def test_livestream_folder_name(clean_settings, username, expected):
    assert fansly_live.folder_name(username) == expected


# ----------------------------------------------------------------------
# Dates and config strings (naming_check.name_safe, space_replacer_ok)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "windows,text,expected",
    [
        (True, "2024-01-01 12:30", "2024-01-01 1230"),
        (False, "2024-01-01 12:30", "2024-01-01 12:30"),
        (True, "a/b\\c\x00d\x7fe", "abcde"),
        (False, "a/b\\c\x00d\x7fe", "ab\\cd\x7fe"),
        (True, "emoji 🔥", "emoji 🔥"),
    ],
)
def test_name_safe_per_platform(monkeypatch, windows, text, expected):
    monkeypatch.setattr(naming_check, "on_windows", lambda: windows)
    assert naming_check.name_safe(text) == expected


@pytest.mark.parametrize(
    "value,ok",
    [
        ("_", True),
        (" ", True),
        ("-", True),
        ("/", False),
        ("\\", False),
        (":", False),
        ("\x7f", False),
        (123, False),
    ],
)
def test_space_replacer_ok(value, ok):
    assert naming_check.space_replacer_ok(value) is ok


# ----------------------------------------------------------------------
# Dots-only names and Windows reserved device names (_safe_parts / _safe_format)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("dots", [".", "..", "...", ". ", " . ", " .. "])
def test_dots_only_value_becomes_underscore(monkeypatch, dots):
    monkeypatch.setattr(placeholder, "_on_windows", lambda: True)
    assert placeholder._safe_parts(f"root/{dots}/file.jpg") == "root/_/file.jpg"


def test_literal_dot_from_template_is_kept(monkeypatch):
    monkeypatch.setattr(placeholder, "_on_windows", lambda: True)
    assert placeholder._safe_format("./{text}/file.jpg", {"text": "..."}) == "./_/file.jpg"
    assert placeholder._safe_format(".", {}) == "."


@pytest.mark.parametrize(
    "name,win_expected",
    [
        ("CON", "CON_"),
        ("con.txt", "con_.txt"),
        ("CON .txt", "CON_ .txt"),
        ("PRN", "PRN_"),
        ("AUX", "AUX_"),
        ("NUL", "NUL_"),
        ("COM1", "COM1_"),
        ("LPT9", "LPT9_"),
        ("COM0", "COM0"),
        ("LPT0", "LPT0"),
        ("console", "console"),
    ],
)
def test_windows_device_names(monkeypatch, name, win_expected):
    monkeypatch.setattr(placeholder, "_on_windows", lambda: True)
    assert placeholder._safe_parts(f"dir/{name}") == f"dir/{win_expected}"

    monkeypatch.setattr(placeholder, "_on_windows", lambda: False)
    assert placeholder._safe_parts(f"dir/{name}") == f"dir/{name}"


# ----------------------------------------------------------------------
# Length limits and truncation (paths.truncate, paths.validate_directory_parts)
# ----------------------------------------------------------------------


def test_windows_truncation_keeps_extension_and_suffix():
    long_name = "a" * 300 + "_1.mp4"
    out = pathlib.PureWindowsPath(str(paths._windows_truncateHelper(f"C:\\media\\{long_name}")))
    assert out.name.endswith("_1.mp4")
    assert paths.get_string_byte_size_windows(out) <= of_env.getattr("WINDOWS_MAX_PATH_BYTES")


def test_windows_truncation_strips_trailing_space_and_dot_without_ext():
    # A name with no extension whose cut lands on trailing spaces/dots
    long_name = "a" * 100 + " . " * 100
    out = pathlib.PureWindowsPath(str(paths._windows_truncateHelper(f"C:\\media\\{long_name}")))
    assert not out.name.endswith((" ", "."))


def test_mac_truncation_respects_nfd_and_utf8():
    # "ǖ" is 2 UTF-8 bytes but 3 UTF-16 code units in NFD
    composed = "ǖ" * 120 + ".mp4"
    out = paths._mac_truncateHelper(f"/data/{composed}")
    assert out.name.endswith(".mp4")
    assert paths._mac_name_size(out.name) <= of_env.getattr("MAC_MAX_PATH")


def test_linux_truncation_keeps_suffix_and_respects_limit():
    long_name = "🔥" * 100 + "_chat.jsonl"
    out = paths._linux_truncateHelper(f"/data/{long_name}", keep_suffix="_chat.jsonl")
    assert out.name.endswith("_chat.jsonl")
    assert paths.get_string_byte_size_unix(out.name) <= of_env.getattr("LINUX_MAX_FILE_NAME_BYTES")


@pytest.mark.parametrize(
    "system,ok_part,too_long_part",
    [
        ("Windows", "a" * 255, "a" * 256),
        ("Darwin", "ǖ" * 85, "ǖ" * 86),
        ("Linux", "a" * 255, "a" * 256),
    ],
)
def test_validate_directory_parts_limits(monkeypatch, system, ok_part, too_long_part):
    monkeypatch.setattr(paths.platform, "system", lambda: system)
    if system == "Linux":
        monkeypatch.setattr(
            of_env,
            "getattr",
            lambda key, default=None, _real=of_env.getattr: (
                255 if key == "LINUX_MAX_FILE_NAME_BYTES" else _real(key, default)
            ),
        )
    paths.validate_directory_parts([ok_part])
    with pytest.raises(ValueError):
        paths.validate_directory_parts([too_long_part])
