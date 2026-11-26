"""Long paths are cut to fit: Windows' 259-character MAX_PATH, Linux's file-name limit."""

import pathlib
import re
import unicodedata

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.utils.paths.paths as paths

# a folder like a real Fansly one, under a Windows home
FOLDER = r"C:\Users\someone\Data\ofscraper\OnlyFans\Fansly\a_creator\Posts\2026-10-31"
CAPTION = "Look at this sunset fading behind the bay! 💀🪄 #fyp #beach #ocean #sky #sunsets " * 3


@pytest.fixture(autouse=True)
def windows_sizes(monkeypatch):
    # the defaults, measured as on Windows whatever runs the test
    monkeypatch.delenv("UTF", raising=False)
    # the settings keep the environment they were last read in, and a test
    # that sets UTF can leave them read with it: read them again without,
    # before the test and after it
    paths.of_env.getkeys(forced=True)
    yield
    monkeypatch.undo()
    paths.of_env.getkeys(forced=True)


def cut(path):
    """The Windows helper's result, read as Windows reads it: CI runs on
    Linux, where a backslash isn't a folder separator."""
    return pathlib.PureWindowsPath(str(paths._windows_truncateHelper(path)))


def windows_chars(path):
    """MAX_PATH counts UTF-16 code units: an emoji takes two."""
    return len(str(path).encode("utf-16-le")) // 2


@pytest.mark.parametrize("ext", [".mp4", ".txt", "_1.jpg"])
def test_a_long_windows_path_fits_in_max_path(ext):
    out = cut(f"{FOLDER}\\2026-10-31 {CAPTION}{ext}")
    assert windows_chars(out) <= 259
    assert out.name.endswith(ext) and str(out.parent) == FOLDER


def test_the_cut_keeps_as_much_of_the_name_as_fits():
    out = cut(f"{FOLDER}\\{'a' * 300}.txt")
    # 259 characters exactly: one more letter would not fit
    assert windows_chars(out) == 259


def test_a_path_that_fits_is_left_alone():
    path = f"{FOLDER}\\2026-10-31 short.mp4"
    assert str(cut(path)) == path


@pytest.mark.parametrize("name, kept", [
    # the extension is removed from the end only, not wherever ".mp4" or
    # ".txt" read as a pattern matches ("-mp4", "ytxt")
    ("clip-mp4 " + "b" * 300 + ".mp4", "clip-mp4 "),
    ("wordytxt " + "b" * 300 + ".txt", "wordytxt "),
])
def test_only_the_real_extension_is_removed(name, kept):
    out = cut(f"{FOLDER}\\{name}")
    assert out.name.startswith(kept)


def test_a_folder_too_long_for_any_name_says_so():
    with pytest.raises(ValueError, match="folder"):
        cut(f"C:\\{'d' * 300}\\name.txt")


def test_a_long_linux_name_fits_in_the_name_limit():
    out = paths._linux_truncateHelper(f"/data/{'a' * 400}.txt")
    size = paths.get_string_byte_size_unix
    # measured as the app measures it; as much as fits, one more letter would not
    assert size(out.name) <= 254 < size("a" + out.name)


@pytest.mark.parametrize("ext", [".mp3", ".3gp", ".3g2", "_2.mp3"])
def test_an_extension_with_digits_is_kept(ext):
    out = cut(f"{FOLDER}\\2026-10-31 {CAPTION}{ext}")
    assert out.name.endswith(ext) and windows_chars(out) <= 259
    out = paths._linux_truncateHelper(f"/data/2026-10-31 {CAPTION * 3}{ext}")
    assert out.name.endswith(ext)


@pytest.mark.parametrize("char", ["é", "я", "日", "’"])
def test_a_non_ascii_name_is_cut_by_windows_own_count(char):
    # one UTF-16 unit each, like a letter: as much fits as of "a"
    out = cut(f"{FOLDER}\\{char * 300}.txt")
    assert windows_chars(out) == 259


def test_an_emoji_counts_as_two_windows_units():
    out = cut(f"{FOLDER}\\{'💀' * 300}.txt")
    assert 258 <= windows_chars(out) <= 259


@pytest.mark.parametrize(
    "folder", ["/Users/someone/d", "/Users/someone/" + "d" * 300], ids=["short", "long"]
)
@pytest.mark.parametrize(
    "name", ["日本語のテキスト" * 16, "💀" * 100, "a" * 300], ids=["cjk", "emoji", "ascii"]
)
def test_a_long_mac_name_fits_in_255_bytes(monkeypatch, folder, name):
    monkeypatch.setattr(paths.platform, "system", lambda: "Darwin")
    out = paths.truncate(f"{folder}/{name}.mp4")
    size = len(out.name.encode("utf-8"))
    # as much as fits: one more character would not
    assert size <= 255 < size + len(name[0].encode("utf-8"))
    assert out.name.endswith(".mp4") and out.parent.as_posix() == folder


def test_a_short_mac_name_is_left_alone(monkeypatch):
    monkeypatch.setattr(paths.platform, "system", lambda: "Darwin")
    path = "/Users/someone/" + "d" * 300 + "/short.mp4"
    assert paths.truncate(path).as_posix() == path


@pytest.mark.parametrize("name", ["💀" * 200 + ".txt", "💀" * 200])
def test_a_folder_that_leaves_no_room_for_a_character_says_so(name):
    # room for 2 bytes after the folder: not one emoji (4), so nothing of the
    # name would be left, giving ".txt", or with no extension the folder itself
    folder = "C:\\" + "d" * (250 if name.endswith(".txt") else 254)
    with pytest.raises(ValueError, match="folder"):
        cut(f"{folder}\\{name}")


@pytest.mark.parametrize("end", [" ", ". ", " . "])
def test_a_cut_without_an_extension_drops_trailing_spaces_and_dots(end):
    # Windows silently drops them from a name; the cut must not end on one
    room = 259 - len(FOLDER) - 1
    kept = "a" * (room - len(end))
    out = cut(f"{FOLDER}\\{kept}{end}{'b' * 300}")
    assert out.name == kept and str(out.parent) == FOLDER


def test_a_cut_that_is_only_spaces_and_dots_says_so():
    room = 259 - len(FOLDER) - 1
    with pytest.raises(ValueError, match="folder"):
        cut(f"{FOLDER}\\{'. ' * room}{'b' * 300}")


def test_a_linux_name_with_no_room_for_a_character_says_so(monkeypatch):
    # room for 2 bytes beside ".txt": not one emoji (4)
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "10")
    with pytest.raises(ValueError, match="no room"):
        paths._linux_truncateHelper(f"/data/{'💀' * 100}.txt")


@pytest.mark.parametrize("end", [" fine.", " fine_1."])
def test_a_bare_trailing_dot_is_not_an_extension(end):
    # a caption ending in "." has no extension: the dot is cut with the rest
    # rather than kept on the end, where Windows would drop it anyway
    name = f"2026-10-31 {CAPTION * 3}{end}"
    assert paths._split_ext(name) == (name, "")
    assert not cut(f"{FOLDER}\\{name}").name.endswith(".")
    assert not paths._linux_truncateHelper(f"/data/{name}").name.endswith(".")


@pytest.mark.parametrize("root", ["C:\\", "\\\\server\\share\\"])
def test_a_name_in_a_drive_or_share_root_gets_all_of_max_path(root):
    # the root already ends with its backslash: it isn't counted twice
    out = cut(f"{root}{'a' * 300}.txt")
    assert windows_chars(out) == 259 and str(out.parent) == root


def test_a_linux_extension_over_the_name_limit_says_so(monkeypatch):
    # nothing of the name to keep, and the extension alone is too long
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "3")
    with pytest.raises(ValueError, match="no room"):
        paths._linux_truncateHelper("/data/.txt")


def test_a_long_dotted_tail_is_not_taken_for_an_extension():
    # a name with no extension whose caption ends ".word...": no real
    # extension is that long, so the tail is cut like the rest of the name
    name = f"2026-10-31 {CAPTION}.{'y' * 300}"
    assert paths._split_ext(name) == (name, "")
    assert str(cut(f"{FOLDER}\\{name}").parent) == FOLDER
    assert paths._linux_truncateHelper(f"/data/{name}").name.startswith("2026-10-31")


@pytest.mark.parametrize("encoding", ["utf-8", "ascii"])
def test_utf_does_not_change_how_windows_counts_a_path(monkeypatch, encoding):
    # the limit is 2 bytes a UTF-16 unit: measured in UTF-8, a path of up to
    # 518 characters would pass, twice what MAX_PATH allows
    monkeypatch.setenv("UTF", encoding)
    out = cut(f"{FOLDER}\\{'a' * 400}.txt")
    assert windows_chars(out) == 259


@pytest.mark.parametrize(
    "name",
    ["💀" * 100 + ".txt", "💀" * 100, ".longext"],
    ids=["ext", "no-ext", "ext-only"],
)
def test_a_mac_name_with_no_room_for_a_character_says_so(monkeypatch, name):
    # room for less than one emoji (4 bytes), or an extension that alone is
    # over the limit: nothing of the name would be left
    monkeypatch.setattr(paths.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("MAC_MAX_PATH", "7" if name.endswith(".txt") else "3")
    with pytest.raises(ValueError, match="no room"):
        paths.truncate(f"/Users/someone/d/{name}")


@pytest.mark.parametrize("char", ["ǖ", "ᾂ", "한"], ids=["latin", "greek", "hangul"])
def test_a_mac_name_fits_hfs_plus_decomposed_form_too(monkeypatch, char):
    # HFS+ stores a name decomposed (NFD) and allows 255 UTF-16 units of it:
    # "ǖ" is 2 bytes of UTF-8 but 3 units decomposed
    monkeypatch.setattr(paths.platform, "system", lambda: "Darwin")
    out = paths.truncate(f"/Volumes/external/d/{char * 300}.mp4")
    nfd = unicodedata.normalize("NFD", out.name)
    assert len(out.name.encode("utf-8")) <= 255
    assert len(nfd.encode("utf-16-le")) // 2 <= 255
    assert out.name.endswith(".mp4") and len(out.name) > 4


# ---------------------------------------------------------------- the caption is cut, not the end (#741)


@pytest.fixture
def name_env(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace

    import ofscraper.classes.placeholder as placeholder

    async def no_script(*a, **k):
        return None

    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(
        placeholder.common_paths, "get_save_location", lambda *a, **k: str(tmp_path / "data")
    )
    monkeypatch.setattr(placeholder.config_file, "open_config", lambda: {})
    monkeypatch.setattr(placeholder.settings, "get_args", lambda: SimpleNamespace())
    monkeypatch.setattr(
        placeholder.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(get_model=lambda _u: None)),
    )
    monkeypatch.setattr(placeholder, "naming_script", no_script)
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: "{date}")
    monkeypatch.setattr(placeholder.data, "get_date", lambda *a, **k: "YYYY-MM-DD")
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")

    def names(file_format, text):
        import ofscraper.classes.of.posts as posts_

        monkeypatch.setattr(placeholder.data, "get_fileformat", lambda *a, **k: file_format)
        raw = {
            "id": 7, "text": text, "price": 0, "isOpened": True, "responseType": "post",
            "postedAt": "2024-05-01T20:00:00+00:00",
            "media": [
                {"id": 70 + i, "type": "photo", "canView": True,
                 "files": {"full": {"url": f"https://example.invalid/photo{i}.jpg"}}}
                for i in range(3)
            ],
        }
        items = posts_.Post(raw, 1, "u", "timeline").all_media
        return [
            asyncio.run(placeholder.Placeholders(item, "jpg").init(create=False)).filepath
            for item in items
        ]

    return names


@pytest.mark.parametrize("file_format, unique", [
    ("{date} {text} {filename}.{ext}", "photo{}"),
    ("{date} {text} {media_id}.{ext}", "7{}"),
])
def test_a_long_caption_is_cut_and_the_unique_part_kept(name_env, file_format, unique):
    out = name_env(file_format, "a long caption " * 40)
    for i, path in enumerate(out):
        assert path.name.endswith(f" {unique.format(i)}.jpg")
        assert path.name.startswith("2024-05-01 a long caption")
        assert paths.get_string_byte_size_unix(path.name) <= 254


def test_a_short_caption_is_left_alone(name_env):
    out = name_env("{date} {text} {filename}.{ext}", "short")
    assert [p.name for p in out] == [f"2024-05-01 short photo{i}.jpg" for i in range(3)]


def test_a_caption_whose_first_character_does_not_fit_is_dropped(name_env, monkeypatch):
    # room for 3 bytes of UTF-8 beside ".jpg": not one emoji (4), so no part
    # of the caption fits, but the name without it does
    monkeypatch.setenv("UTF", "utf-8")
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "7")
    out = name_env("{text} {media_id}.{ext}", "💀" * 100)
    assert [p.name for p in out] == [f" {70 + i}.jpg" for i in range(3)]


def test_a_caption_cut_to_nothing_keeps_an_underscored_unique_part(name_env, monkeypatch):
    # "_70.jpg" looks like a "_1"-style number and an extension, but it's a
    # name: with no room for the caption, the media id is still kept
    monkeypatch.setenv("UTF", "utf-8")
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "7")
    out = name_env("{text}_{media_id}.{ext}", "💀" * 100)
    assert [p.name for p in out] == [f"_{70 + i}.jpg" for i in range(3)]


def test_a_caption_is_not_cut_to_a_name_with_nothing_before_the_extension(
    name_env, monkeypatch
):
    # with {text} alone, an empty caption would leave a nameless ".jpg";
    # the name is left to the cut, which says there's no room instead
    monkeypatch.setenv("UTF", "utf-8")
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "7")
    with pytest.raises(ValueError, match="no room"):
        name_env("{text}.{ext}", "💀" * 100)


@pytest.mark.parametrize("file_format", ["{text}.mp3", "{text}.3gp"])
def test_a_caption_is_not_cut_to_nothing_before_an_extension_with_digits(
    name_env, monkeypatch, file_format
):
    # ".mp3" is an extension too: an empty caption would leave the "_1.mp3"
    # a count makes of it, which repeats in every post. The name is left to
    # the cut instead (which, reading such extensions as #799 does, says
    # there's no room)
    monkeypatch.setenv("UTF", "utf-8")
    monkeypatch.setenv("LINUX_MAX_FILE_NAME_BYTES", "7")
    try:
        out = name_env(file_format, "💀" * 100)
    except ValueError as error:
        assert "no room" in str(error)
        return
    assert not [p.name for p in out if re.fullmatch(r"_[0-9]+\.[a-z0-9]+", p.name)]


def test_the_caption_is_left_whole_when_truncation_is_off(name_env, monkeypatch):
    # --original or truncation_default: false: the caption isn't shortened
    # (#756 then keeps the whole path)
    import ofscraper.classes.placeholder as placeholder

    # the settings object is a dict read by attribute
    monkeypatch.setitem(placeholder.settings.get_settings(), "trunicate", False)

    def shortened(*a, **k):
        raise AssertionError("the caption was shortened")

    monkeypatch.setattr(placeholder.Placeholders, "_name_with_text", shortened)
    name_env("{date} {text} {filename}.{ext}", "a long caption " * 40)


@pytest.mark.parametrize("system, key", [("Linux", "LINUX_MAX_FILE_NAME_BYTES"), ("Darwin", "MAC_MAX_PATH")])
def test_a_folder_name_is_checked_against_the_limit_names_are_cut_to(monkeypatch, system, key):
    """A lowered limit (an encrypted share allows 143 bytes) applies to the
    livestream folder names checked, as to the file names cut"""
    real = paths.of_env.getattr
    monkeypatch.setattr(paths.platform, "system", lambda: system)
    monkeypatch.setattr(paths.of_env, "getattr", lambda k, *a, **kw: 143 if k == key else real(k, *a, **kw))

    paths.validate_directory_parts(["a" * 143])
    with pytest.raises(ValueError):
        paths.validate_directory_parts(["a" * 144])
