"""Filename extensions, placeholders, and text-file output."""

# ----------------------------------------------------------------------
# From test_extension_from_content_type.py
# A saved file's extension comes from the reply's Content-Type. The subtype
# is usually the extension, but not always: a QuickTime video was saved as
# ".quicktime", which players don't recognise.
# ----------------------------------------------------------------------

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
from ofscraper.commands.scraper.actions.utils.general import extension_for


@pytest.mark.parametrize(
    "content_type, ext",
    [
        ("video/mp4", "mp4"),
        ("image/jpeg", "jpeg"),  # unchanged: existing image names keep .jpeg
        ("audio/mp4", "mp4"),
        ("video/quicktime", "mov"),
        ("video/x-ms-wmv", "wmv"),
        ("video/x-msvideo", "avi"),
        ("video/x-matroska", "mkv"),
        ("video/mp2t", "ts"),
        ("Video/QuickTime", "mov"),
        ("video/mp4; charset=binary", "mp4"),
        ("wmv", "wmv"),  # a bare value some CDNs echo back from the link
    ],
)
def test_extension_for(content_type, ext):
    assert extension_for(content_type, "fallback") == ext


@pytest.mark.parametrize(
    "content_type", [None, "", "application/octet-stream", "binary/octet-stream"]
)
def test_missing_or_generic_type_uses_the_fallback(content_type):
    assert extension_for(content_type, "mp4") == "mp4"

# ----------------------------------------------------------------------
# From test_my_id_placeholder.py
# {my_id} holds the account's numeric id, not its display name (#206).
# ----------------------------------------------------------------------

from types import SimpleNamespace

import pytest

import ofscraper.classes.placeholder as placeholder


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setattr(placeholder.profile_data, "get_my_info", lambda: {"id": 12345, "name": "Display Name", "username": "me_user"})
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_save_location", lambda *a, **k: "/data")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: "/cfg")
    monkeypatch.setattr(placeholder, "site_save_location", lambda: "/data")


def _variables(monkeypatch, anon):
    fake = SimpleNamespace(anon=anon)
    monkeypatch.setattr(placeholder.settings, "get_settings", lambda: fake)
    monkeypatch.setattr(placeholder.me.settings, "get_settings", lambda: fake)
    p = placeholder.basePlaceholder()
    p.create_variables_base()
    return p._variables


def test_my_id_is_the_account_id(base, monkeypatch):
    v = _variables(monkeypatch, anon=False)
    assert v["my_id"] == 12345
    assert v["my_username"] == "me_user"


def test_my_id_in_anon_mode(base, monkeypatch):
    v = _variables(monkeypatch, anon=True)
    assert v["my_id"] == "anon"
    assert v["my_username"] == "anon"

# ----------------------------------------------------------------------
# A text file is named with the same file_format as media, so it has every
# placeholder a media file has (#742).
# ----------------------------------------------------------------------

from naming_helpers import naming  # noqa: F401  (fixture)


def test_a_text_file_has_the_media_only_placeholders(naming):
    text, (media,) = naming(
        "{media_id} {mediaid} {download_type} {downloadtype} {text}.{ext}", "hello"
    )
    assert media == "70 70 Normal Normal hello.jpg"
    # no media: the post's id stands in for the media id
    assert text == "8 8 Normal Normal hello.txt"


def test_a_text_file_has_every_placeholder_a_media_file_has(naming, monkeypatch):
    seen = {}
    for cls in (placeholder.Placeholders, placeholder.Textholders):
        real = cls.createfilename

        async def recorded(self, real=real, cls=cls):
            out = await real(self)
            seen[cls.__name__] = set(self._variables)
            return out

        monkeypatch.setattr(cls, "createfilename", recorded)
    naming("{filename}.{ext}", "hello")
    assert seen["Placeholders"] - seen["Textholders"] == set()

# ----------------------------------------------------------------------
# From test_paid_placeholder_models.py
# ----------------------------------------------------------------------

import ofscraper.managers.model as model_manager
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.classes.of.models import Model


def _placeholder():
    return f"{of_env.getattr('DELETED_MODEL_PLACEHOLDER')}_123"


def test_placeholder_models_are_left_out_of_the_scrape_selection(monkeypatch):
    for module, name in [
        (model_manager.subtype, "subType"),
        (model_manager.price, "pricePaidFreeFilterHelper"),
        (model_manager.flags, "promoFilterHelper"),
        (model_manager.date_, "dateFilters"),
        (model_manager.other, "otherFilters"),
    ]:
        monkeypatch.setattr(module, name, lambda models: models)
    manager = model_manager.ModelManager()
    # what --scrape-paid adds for a deleted account, beside a real subscription
    manager._update_all_subs(
        [
            Model({"username": "model", "id": 1, "avatar": None}),
            Model({"username": _placeholder(), "id": _placeholder()}),
        ]
    )

    assert [m.name for m in manager._apply_filters()] == ["model"]
    assert manager.get_model(_placeholder()) is not None  # still there for the paid pass


def test_placeholder_model_has_no_avatar_or_header():
    placeholder = Model({"username": _placeholder(), "id": _placeholder()})
    assert placeholder.avatar is None and placeholder.header is None

# ----------------------------------------------------------------------
# A post's media are told apart by a count before the extension when the
# file_format has nothing unique per media (#743).
# ----------------------------------------------------------------------

import re

from naming_helpers import naming  # noqa: F401  (fixture)


def test_the_count_goes_before_the_extension_only(naming, monkeypatch):
    monkeypatch.setattr(placeholder.data, "get_date", lambda *a, **k: "DD.MM.YYYY")
    _, media = naming(
        "{date} {text}.{ext}", "Hello there. How are you... fine", media=2
    )
    assert media == [
        "31.10.2026 Hello there. How are you... fine_1.jpg",
        "31.10.2026 Hello there. How are you... fine_2.jpg",
    ]


def test_the_count_ends_a_name_with_no_extension(naming):
    _, media = naming("{post_id}", "hello", media=2)
    assert media == ["8_1", "8_2"]


@pytest.mark.parametrize(
    "name",
    ["filename", "file_name", "only_filename", "only_file_name", "onlyfilename",
     "original_filename", "originalfilename", "media_id", "mediaid"],
)
def test_no_count_when_the_name_is_already_unique(naming, name):
    # every spelling of a placeholder that differs per media, not only some
    _, media = naming("{%s}.{ext}" % name, "hello", media=2, text=False)
    assert not any(re.search(r"_[12]\.jpg$", item) for item in media), media
    assert len(set(media)) == 2

# ----------------------------------------------------------------------
# From test_text_file.py
# ----------------------------------------------------------------------

import asyncio
import textwrap
from types import SimpleNamespace

import aiofiles

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.utils.text as text


class _Post:
    def __init__(self, caption):
        self.text = caption
        self.downloaded = None

    def mark_text_download_attempt(self):
        pass

    def mark_text_downloaded(self, ok):
        self.downloaded = ok


def _write(monkeypatch, tmp_path, caption):
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

    real_open = aiofiles.open

    def cp1252_default_open(*args, encoding=None, **kwargs):
        # what open() does on Windows before Python 3.15
        return real_open(*args, encoding=encoding or "cp1252", **kwargs)

    monkeypatch.setattr(text.placeholder, "Textholders", _Holder)
    monkeypatch.setattr(text, "after_download_script", _no_script)
    monkeypatch.setattr(text.aiofiles, "open", cp1252_default_open)
    monkeypatch.setattr(
        text.settings,
        "get_settings",
        lambda: SimpleNamespace(force_all=False, force_model_unique=False),
    )
    post = _Post(caption)
    asyncio.run(text.get_text_process("model", post))
    return post, path


# Two posts whose text files get the same name both keep their text (#746):
# real settings, real posts and the real placeholder classes.

from naming_helpers import make_post, naming, text_files  # noqa: F401  (fixture)


def _write_texts(naming, monkeypatch, captions, *options, collision="media_id"):
    async def no_script(path):
        pass

    naming("{filename}.{ext}", "x", "--text-type", "word", "--textlength", "2", *options)
    monkeypatch.setattr(text, "after_download_script", no_script)
    monkeypatch.setattr(
        text.config_data, "get_filename_collision", lambda *a, **k: collision
    )
    posts = [make_post(caption, 0, post_id=n) for n, caption in enumerate(captions, 8)]
    asyncio.run(text.get_text("u", posts))


CAPTIONS = ["Good morning everyone", "Good morning to my fans"]


def test_a_taken_text_file_name_gets_the_post_id(naming, monkeypatch, tmp_path):
    _write_texts(naming, monkeypatch, CAPTIONS)
    both = {"Good morning.txt": CAPTIONS[0], "Good morning_9.txt": CAPTIONS[1]}
    assert text_files(tmp_path) == both
    # a second run finds each post's own file, and writes nothing new
    _write_texts(naming, monkeypatch, CAPTIONS)
    assert text_files(tmp_path) == both
    # --force-all rewrites each post's own file, not the other post's
    _write_texts(naming, monkeypatch, CAPTIONS, "--force-all")
    assert text_files(tmp_path) == both


def _write_post_text(naming, monkeypatch, file_format, caption, post_id, *options):
    async def no_script(path):
        pass

    naming(file_format, "x", *options)
    monkeypatch.setattr(text, "after_download_script", no_script)
    monkeypatch.setattr(
        text.config_data, "get_filename_collision", lambda *a, **k: "media_id"
    )
    asyncio.run(text.get_text("u", [make_post(caption, 0, post_id=post_id)]))


@pytest.mark.parametrize(
    "file_format", ["{post_id}.{ext}", "{date}_{post_id}.{ext}", "{postid}.{ext}"]
)
def test_a_name_with_the_post_id_is_that_posts_own_file(
    naming, monkeypatch, tmp_path, file_format
):
    _write_post_text(naming, monkeypatch, file_format, "old caption", 8)
    (name,) = text_files(tmp_path)
    # the creator edits the caption: a plain run keeps the file as it is,
    # and --force-all rewrites it in place, not as name_8
    _write_post_text(naming, monkeypatch, file_format, "new caption", 8)
    assert text_files(tmp_path) == {name: "old caption"}
    _write_post_text(
        naming, monkeypatch, file_format, "new caption", 8, "--force-all"
    )
    assert text_files(tmp_path) == {name: "new caption"}


@pytest.mark.parametrize("prefix", ["18", "2026-08", "80"])
def test_a_number_that_only_contains_the_post_id_is_not_its_own(
    naming, monkeypatch, tmp_path, prefix
):
    # another post's file holds the name post 8's text resolves to
    file_format = prefix + " {text}.{ext}"
    _write_post_text(naming, monkeypatch, file_format, "same", 18)
    _write_post_text(naming, monkeypatch, file_format, "same here", 8, "-tt", "word", "-tl", "1")
    assert text_files(tmp_path) == {
        f"{prefix} same.txt": "same",
        f"{prefix} same_8.txt": "same here",
    }


@pytest.mark.parametrize("file_format, post_id, other", [
    # the post id is a number in the caption, or in the date
    ("{text}.{ext}", 8, "Top 8"),
    ("{date} {text}.{ext}", 31, "2026-10-31 Top 8"),
])
def test_a_number_in_the_name_that_is_not_from_post_id_is_not_its_own(
    naming, monkeypatch, tmp_path, file_format, post_id, other
):
    options = ("-tt", "word", "-tl", "2")
    _write_post_text(naming, monkeypatch, file_format, "Top 8 looks", 18, *options)
    _write_post_text(naming, monkeypatch, file_format, "Top 8 picks", post_id, *options)
    assert text_files(tmp_path) == {
        f"{other}.txt": "Top 8 looks",
        f"{other}_{post_id}.txt": "Top 8 picks",
    }


def test_a_hand_edited_text_file_is_kept_at_either_name(naming, monkeypatch, tmp_path):
    _write_texts(naming, monkeypatch, CAPTIONS)
    folder = next((tmp_path / "data").rglob("Good morning.txt")).parent
    for name in ("Good morning.txt", "Good morning_9.txt"):
        (folder / name).write_text("edited by hand", encoding="utf-8")
    # a plain run writes over neither file
    _write_texts(naming, monkeypatch, CAPTIONS)
    edited = {name: text_files(tmp_path)[name] for name in ("Good morning.txt", "Good morning_9.txt")}
    assert edited == {"Good morning.txt": "edited by hand", "Good morning_9.txt": "edited by hand"}


def test_the_same_caption_twice_is_one_text_file(naming, monkeypatch, tmp_path):
    _write_texts(naming, monkeypatch, ["Good morning", "Good morning"])
    assert text_files(tmp_path) == {"Good morning.txt": "Good morning"}


def test_a_fallback_name_that_is_another_posts_text_is_not_used(
    naming, monkeypatch, tmp_path
):
    # post 9's caption gives it the name post 10 falls back to
    captions = ["Good morning everyone", "Good morning_10 starts now", CAPTIONS[1]]
    files = {
        "Good morning.txt": captions[0],
        "Good morning_10.txt": captions[1],
        "Good morning_10_2.txt": captions[2],
    }
    _write_texts(naming, monkeypatch, captions)
    assert text_files(tmp_path) == files
    # a second run finds post 10's file, and --force-all rewrites only it
    for options in ((), ("--force-all",)):
        _write_texts(naming, monkeypatch, captions, *options)
        assert text_files(tmp_path) == files


def test_overwrite_mode_keeps_the_first_text_file(naming, monkeypatch, tmp_path):
    _write_texts(naming, monkeypatch, CAPTIONS, collision="overwrite")
    assert list(text_files(tmp_path)) == ["Good morning.txt"]


LONG = (
    "Good morning everyone, this caption is long enough to wrap onto a "
    "second line in the text file"
)


def _rerun_over_older_file(naming, monkeypatch, tmp_path, caption, data):
    """Saves data where the post's text file goes, as a version before #133
    did, runs again, and returns the folder's files: name -> text."""
    _write_texts(naming, monkeypatch, [caption])
    (path,) = (tmp_path / "data").rglob("*.txt")
    path.write_bytes(data)
    _write_texts(naming, monkeypatch, [caption])
    return {p.name: p.read_text(encoding="utf-8") for p in path.parent.iterdir()}


def test_a_text_file_from_before_133_is_rewritten_in_place(
    naming, monkeypatch, tmp_path
):
    # versions before #133 ran the wrapped lines together
    older = "".join(textwrap.wrap(LONG, width=70)).encode()
    files = _rerun_over_older_file(naming, monkeypatch, tmp_path, LONG, older)
    assert files == {"Good morning.txt": text.file_text(LONG)}


def test_a_windows_text_file_from_before_133_is_rewritten_in_place(
    naming, monkeypatch, tmp_path
):
    # written in the Windows code page, and stopped at the line with an
    # emoji, which that code page can't encode
    caption = "Good morning café " + LONG + " \U0001f525 now"
    lines = textwrap.wrap(caption, width=70)
    assert "\U0001f525" in lines[1]
    older = lines[0].encode("cp1252")
    monkeypatch.setattr("locale.getpreferredencoding", lambda *a: "cp1252")
    files = _rerun_over_older_file(naming, monkeypatch, tmp_path, caption, older)
    assert files == {"Good morning.txt": text.file_text(caption)}

def test_caption_with_emoji_is_written(monkeypatch, tmp_path):
    post, path = _write(monkeypatch, tmp_path, "new set out now \U0001f525✨")
    assert post.downloaded is True
    assert path.read_text(encoding="utf-8") == "new set out now \U0001f525✨"


def test_wrapped_caption_keeps_line_breaks(monkeypatch, tmp_path):
    caption = " ".join(["word"] * 30)  # 149 characters, wraps at 70
    post, path = _write(monkeypatch, tmp_path, caption)
    written = path.read_text(encoding="utf-8")
    assert written.replace("\n", " ") == caption
    assert "wordword" not in written

# ----------------------------------------------------------------------
# A caption can't change the folder a file is saved in (#739). A backslash
# is a folder separator on Windows, and a tab or a carriage return can't be
# in a Windows file name.
# ----------------------------------------------------------------------

import ntpath
import re

from naming_helpers import naming  # noqa: F401  (fixture)

FOLDER = r"C:\data\a_creator\Posts"


@pytest.mark.parametrize(
    "caption",
    [r"me \ you", r"up\..\..\..\and out", "a tab\there", "a return\r\nhere"],
)
def test_a_caption_cannot_name_another_folder(naming, caption):
    text, (media,) = naming("{date} {filename} {text}.{ext}", caption)
    for name in (text, media):
        assert not re.search(r"[\\\x00-\x1f]", name)
        # as Windows reads it: still a file in the folder it was meant for
        assert ntpath.dirname(ntpath.normpath(ntpath.join(FOLDER, name))) == FOLDER


def test_a_text_file_named_by_its_caption_stays_in_its_folder(naming):
    # the default file_format: a text file's {filename} is its caption
    text, _ = naming("{filename}.{ext}", r"..\..\..\elsewhere")
    assert ntpath.dirname(ntpath.normpath(ntpath.join(FOLDER, text))) == FOLDER


# A caption or name can't be "." or "..", or a name Windows keeps for a
# device (CON, NUL, COM1, ...), as a whole folder or file name.
import asyncio

from naming_helpers import make_post


@pytest.mark.parametrize("caption", [".", "..", "..."])
def test_a_caption_of_dots_is_not_a_folder_name(naming, caption):
    # "{text}/" makes the caption a folder: ".." would be the folder above
    text, (media,) = naming("{text}/{filename}.{ext}", caption)
    for name in (text, media):
        assert not any(re.fullmatch(r"\.+", part) for part in re.split(r"[/\\]", name))
        assert ntpath.dirname(ntpath.normpath(ntpath.join(FOLDER, name))).startswith(FOLDER + "\\")


def test_a_caption_of_dots_does_not_name_another_save_folder(naming, monkeypatch, tmp_path):
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: "{text}")
    naming("{filename}.{ext}", "..", text=False)
    post = make_post("..")
    folder = asyncio.run(placeholder.Placeholders(post.all_media[0], "jpg").getmediadir(create=False))
    assert folder.parent == tmp_path / "data"


@pytest.mark.parametrize("caption", ["CON", "nul", "Aux", "PRN", "COM1", "lpt9", "con.backup"])
@pytest.mark.parametrize("file_format", ["{text}.{ext}", "{filename}.{ext}", "{text}/{date}.{ext}"])
def test_a_windows_device_name_is_not_a_file_name(naming, monkeypatch, caption, file_format):
    monkeypatch.setattr(placeholder, "_on_windows", lambda: True)
    text, (media,) = naming(file_format, caption)
    names = [text] if file_format == "{filename}.{ext}" else [text, media]
    for name in names:
        for part in re.split(r"[/\\]", name):
            stem = part.split(".")[0].rstrip(" ")
            assert stem.upper() not in WINDOWS_DEVICES, name


@pytest.mark.parametrize("cls", ["Placeholders", "Textholders"])
def test_a_device_name_is_kept_outside_windows(naming, monkeypatch, tmp_path, cls):
    # Linux and macOS have no device names: a creator folder named "aux" or
    # a caption "CON" keeps the name it had
    monkeypatch.setattr(placeholder, "_on_windows", lambda: False)
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: "aux/{text}")
    text, (media,) = naming("{text}.{ext}", "CON")
    assert (text, media) == ("CON.txt", "CON.jpg")
    post = make_post("CON")
    ele = post.all_media[0] if cls == "Placeholders" else post
    path = asyncio.run(getattr(placeholder, cls)(ele, "jpg").getmediadir(create=False))
    assert path == tmp_path / "data" / "aux" / "CON"


@pytest.mark.parametrize(
    "system, windows", [("Windows", True), ("Linux", False), ("Darwin", False)]
)
def test_on_windows_follows_the_system(monkeypatch, system, windows):
    monkeypatch.setattr(placeholder.platform, "system", lambda: system)
    assert placeholder._on_windows() is windows


def test_a_name_that_only_starts_like_a_device_is_unchanged(naming):
    text, (media,) = naming("{text}.{ext}", "Contest")
    assert (text, media) == ("Contest.txt", "Contest.jpg")


WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{d}{n}" for d in ("COM", "LPT") for n in range(1, 10)
}


@pytest.mark.parametrize("cls", ["Placeholders", "Textholders"])
@pytest.mark.parametrize("dir_format,folder", [(".", ""), ("./{text}/.", "a caption")])
def test_a_dir_format_of_a_dot_still_saves_in_the_save_location(naming, monkeypatch, tmp_path, cls, dir_format, folder):
    # dir_format "." is how a user saves straight into save_location
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: dir_format)
    naming("{filename}.{ext}", "a caption", text=False)
    post = make_post("a caption")
    ele = post.all_media[0] if cls == "Placeholders" else post
    path = asyncio.run(getattr(placeholder, cls)(ele, "jpg").getmediadir(create=False))
    assert path == tmp_path / "data" / folder


@pytest.mark.parametrize("caption", [". ", ".. ", ". .", "..  ", " .", " .. "])
def test_a_caption_of_dots_and_spaces_is_not_a_folder_name(naming, caption):
    # Windows drops the trailing spaces and dots, leaving "." or ".." or nothing
    text, (media,) = naming("{text}/{filename}.{ext}", caption)
    for name in (text, media):
        assert not any(re.fullmatch(r"\s*\.[.\s]*", part) for part in re.split(r"[/\\]", name))


def test_a_file_format_of_a_dot_folder_is_kept(naming):
    # "./" written in file_format is the folder itself, not a caption's dots
    text, (media,) = naming("./{text}.{ext}", "a caption")
    assert (text, media) == ("./a caption.txt", "./a caption.jpg")


def test_a_dot_folder_file_format_is_kept_when_the_name_is_not_the_template_filled_in():
    # a text file's name built otherwise than by filling in file_format (#738
    # leaves {filename} out beside {text}): the "./" file_format writes before
    # any placeholder is still its own, not a caption's dots
    variables = {"text": "a caption", "filename": "a caption", "ext": "txt"}
    out = placeholder._safe_name("./a caption.txt", "./{text} {filename}.{ext}", variables)
    assert out == "./a caption.txt"
    # a caption's own dots after it are still not a folder
    out = placeholder._safe_name("./../a.txt", "./{text}/{filename}.{ext}", variables)
    assert out == "./_/a.txt"


import asyncio
import json

from ofscraper.classes.of.posts import Post


@pytest.fixture
def path_options(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    config = {"file_options": {"save_location": str(tmp_path / "downloads"),
                               "dir_format": "{model_username}", "file_format": "{filename}.{ext}"},
              "advanced_options": {"temp_dir": ""}}
    def save():
        path.write_text(json.dumps(config), encoding="utf-8")
    save()
    monkeypatch.setattr(placeholder.config_file, "open_config", lambda: json.loads(path.read_text(encoding="utf-8")))
    real = placeholder.settings.get_settings()
    monkeypatch.setattr(placeholder.settings, "get_settings", lambda: SimpleNamespace(**{**dict(real), "site": "fansly", "anon": True}))
    monkeypatch.setattr(placeholder.manager, "Manager", SimpleNamespace(
        current_model_manager=SimpleNamespace(get_model=lambda username: None)))
    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    original = of_env.getattr
    monkeypatch.setattr(of_env, "getattr", lambda key, *a, **k: True if key == "FILE_COUNT_PLACEHOLDER" else original(key, *a, **k))
    return config, save


def _two_media_post():
    return Post({"id": 7, "postedAt": "2024-05-01T20:00:00Z", "text": "test", "media": [
        {"id": i, "type": "photo", "canView": True,
         "files": {"full": {"url": f"https://cdn.example.invalid/{i}.jpg"}}}
        for i in (101, 102)
    ]}, 123, "test_creator", "Timeline")


@pytest.mark.parametrize("temp_root", [None, "", "explicit"])
def test_temp_root_falls_back_only_when_empty(path_options, tmp_path, temp_root):
    config, save = path_options
    configured = str(tmp_path / "temp") if temp_root == "explicit" else temp_root
    config["advanced_options"]["temp_dir"] = configured
    save()
    holder = placeholder.Placeholders(_two_media_post().all_media[0], "jpg")
    result = asyncio.run(holder.getmediadir(root=placeholder.data.get_TempDir(), create=False))
    root = tmp_path / "temp" if temp_root == "explicit" else tmp_path / "downloads" / "Fansly"
    assert result == root / "test_creator"


@pytest.mark.parametrize("kind", ["media", "caption"])
def test_absolute_media_and_caption_folders_normalize_under_the_save_root(path_options, tmp_path, kind):
    config, save = path_options
    config["file_options"]["dir_format"] = "/../streams"
    save()
    post = _two_media_post()
    holder = (placeholder.Placeholders(post.all_media[0], "jpg") if kind == "media"
              else placeholder.Textholders(post, "txt"))
    assert asyncio.run(holder.getmediadir(create=False)) == tmp_path / "downloads" / "Fansly" / "streams"


@pytest.mark.parametrize("global_format,type_format,expected", [
    ("{filename}.{ext}", "{post_id}.{ext}", ["7_1.jpg", "7_2.jpg"]),
    ("{post_id}.{ext}", "{media_id}.{ext}", ["101.jpg", "102.jpg"]),
    ("{post_id}.{ext}", None, ["7_1.jpg", "7_2.jpg"]),
])
def test_type_filename_controls_automatic_numbering(path_options, global_format, type_format, expected):
    config, save = path_options
    config["file_options"]["file_format"] = global_format
    config["type_options"] = {"images": {"file_format": type_format}} if type_format else {}
    save()
    names = [asyncio.run(placeholder.Placeholders(ele, "jpg").createfilename())
             for ele in _two_media_post().all_media]
    assert names == expected


def test_live_defaults_do_not_fetch_unused_account_identity(path_options, monkeypatch, tmp_path):
    import datetime

    def unexpected():
        raise AssertionError("Default livestream templates do not need account identity")

    monkeypatch.setattr(placeholder.me, "parse_user", unexpected)
    when = datetime.datetime(2024, 5, 1, tzinfo=datetime.timezone.utc)
    result = placeholder.live_recording_path(tmp_path, "test_creator", when, site_name="OnlyFans", ext="webm", model_id=123)
    assert result == tmp_path / "OnlyFans" / "test_creator" / "Livestreams" / "test_creator_20240501_000000_live.webm"


@pytest.mark.parametrize("alias", [False, True])
def test_live_account_placeholders_share_base_context(path_options, monkeypatch, tmp_path, alias):
    import datetime

    config, save = path_options
    config["live_options"] = {"dir_format": "{myid}/{myusername}" if alias else "{my_id}/{my_username}"}
    save()
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("Test account", "test_account"))
    when = datetime.datetime(2024, 5, 1, tzinfo=datetime.timezone.utc)
    result = placeholder.live_recording_path(tmp_path, "test_creator", when, site_name="Fansly", ext="mp4", model_id=123)
    assert result.parent == tmp_path / "Fansly" / "anon" / "test_account"


def test_live_requested_identity_errors_are_not_silently_formatted(path_options, monkeypatch, tmp_path):
    import datetime

    config, save = path_options
    config["live_options"] = {"dir_format": "{my_id}"}
    save()

    def unavailable():
        raise RuntimeError("test account lookup failed")

    monkeypatch.setattr(placeholder.me, "parse_user", unavailable)
    with pytest.raises(RuntimeError, match="test account lookup failed"):
        placeholder.live_recording_path(tmp_path, "test_creator", datetime.datetime(2024, 5, 1), site_name="OnlyFans", ext="webm")


# ----------------------------------------------------------------------
# Review of #850: type_options and live_options paths
# ----------------------------------------------------------------------

import datetime as _dt

_STARTED = _dt.datetime(2024, 5, 1, tzinfo=_dt.timezone.utc)
_DEFAULT_LIVE = ("OnlyFans", "test_creator", "Livestreams", "test_creator_20240501_000000_live.webm")


def test_text_clash_check_uses_the_text_file_template(path_options, tmp_path):
    # the global name has {post_id}, the text file's own doesn't: another
    # post's caption at the name means this post's text goes elsewhere
    from ofscraper.utils import text

    config, save = path_options
    config["file_options"]["file_format"] = "{post_id}_{text}.{ext}"
    config["type_options"] = {"text": {"file_format": "{text}.{ext}"}}
    save()
    post = _two_media_post()
    taken = tmp_path / "test.txt"
    taken.write_text("another post's caption", encoding="utf-8")
    formats = placeholder.Textholders(post, "txt").templates()[1:]
    assert text._own_path(taken, post, "test", formats=formats) == tmp_path / "test_7.txt"


def test_live_templates_take_the_date_parts(path_options, tmp_path):
    config, save = path_options
    config["live_options"] = {
        "dir_format": "{sitename}/{model_username}/{year}/{month}",
        "file_format": "{day}_{model_username}",
    }
    save()
    result = placeholder.live_recording_path(
        tmp_path, "test_creator", _STARTED, site_name="OnlyFans", ext="webm"
    )
    assert result == tmp_path / "OnlyFans" / "test_creator" / "2024" / "05" / "01_test_creator_20240501_000000.webm"


@pytest.mark.parametrize("template", ["{post_id}", "{modelObj.name}", "{date"])
def test_a_live_template_that_cannot_be_filled_in_falls_back(path_options, monkeypatch, tmp_path, template):
    # the stream is still recorded, under the default name, with a warning
    config, save = path_options
    config["live_options"] = {"file_format": template}
    save()
    warnings = []
    monkeypatch.setattr(placeholder.log, "warning", warnings.append)
    result = placeholder.live_recording_path(
        tmp_path, "test_creator", _STARTED, site_name="OnlyFans", ext="webm"
    )
    assert result == tmp_path.joinpath(*_DEFAULT_LIVE)
    assert len(warnings) == 1 and "test_creator's recording uses the default name" in warnings[0]


@pytest.mark.parametrize("template", ["/tmp/sibling/{date}", "../{date}"])
def test_a_live_file_template_with_a_path_keeps_the_recording_folder(path_options, tmp_path, template):
    config, save = path_options
    config["live_options"] = {"dir_format": "{sitename}/recordings", "file_format": template}
    save()
    result = placeholder.live_recording_path(
        tmp_path, "test_creator", _STARTED, site_name="OnlyFans", ext="webm"
    )
    assert result == tmp_path / "OnlyFans" / "recordings" / _DEFAULT_LIVE[-1]


def test_an_overlong_live_directory_component_uses_the_default_folder(path_options, monkeypatch, tmp_path):
    config, save = path_options
    config["live_options"] = {"dir_format": "recordings/" + "é" * 128 + "/{username}"}
    save()
    monkeypatch.setattr(placeholder.paths.platform, "system", lambda: "Linux")
    result = placeholder.live_recording_path(
        tmp_path, "test_creator", _STARTED, site_name="OnlyFans", ext="webm"
    )
    assert result == tmp_path.joinpath(*_DEFAULT_LIVE)
    result.parent.mkdir(parents=True)


def test_live_path_values_cannot_climb_folders(path_options, tmp_path):
    result = placeholder.live_recording_path(
        tmp_path, "..", _STARTED, site_name="OnlyFans", ext="webm"
    )
    assert result.parent == tmp_path / "OnlyFans" / "_" / "Livestreams"


def test_an_override_save_location_gets_the_fansly_folder_as_save_location_does(path_options, tmp_path):
    config, save = path_options
    base = tmp_path / "Fansly"
    config["file_options"]["save_location"] = str(base)
    config["type_options"] = {"images": {"save_location": str(base)}}
    save()
    ele = _two_media_post().all_media[0]
    assert placeholder.default_media_root() == base / "Fansly"
    assert placeholder.Placeholders(ele, "jpg").templates()[0] == base / "Fansly"


def test_templates_are_worked_out_once_per_file(path_options, monkeypatch):
    reads = []
    real = placeholder.data.get_type_options
    monkeypatch.setattr(
        placeholder.data, "get_type_options", lambda *a, **k: reads.append(1) or real(*a, **k)
    )
    holder = placeholder.Placeholders(_two_media_post().all_media[0], "jpg")
    asyncio.run(holder.getmediadir(create=False))
    asyncio.run(holder.createfilename())
    assert len(reads) == 1


def test_startup_check_names_live_and_type_templates(path_options):
    from ofscraper.utils.config import naming_check

    config, save = path_options
    config["live_options"] = {"dir_format": "{post_id}"}
    config["type_options"] = {
        "videos": {"file_format": "{nope}.{ext}"},
        "livestreams": {"file_format": "{text}"},
        "images": {"dir_format": "{post_id}"},
    }
    save()
    lines = naming_check.problems()
    live = "Livestreams are recorded under the default name until it's fixed"
    assert f'live_options.dir_format "{{post_id}}" has an unknown placeholder: {{post_id}}. {live}' in lines
    assert f'type_options.livestreams.file_format "{{text}}" has an unknown placeholder: {{text}}. {live}' in lines
    assert any(line.startswith('type_options.videos.file_format "{nope}.{ext}"') for line in lines)
    assert not any(line.startswith("type_options.images") for line in lines)


def test_unique_name_warning_checks_type_file_formats(path_options):
    from ofscraper.commands.scraper.utils import prepare

    config, save = path_options
    config["type_options"] = {"videos": {"file_format": "{date}.{ext}"}}
    save()
    assert prepare.check_uniquename() is False
    # livestream names hold the start time; they aren't checked
    config["type_options"] = {"livestreams": {"file_format": "{date}"}}
    save()
    assert prepare.check_uniquename() is True


def test_startup_check_covers_full_paths_dates_and_type_names(path_options):
    from ofscraper.utils.config import naming_check

    config, save = path_options
    config["file_options"]["date"] = "YYYY/MM"
    config["responsetype"] = {"timeline": "Wall"}
    config["type_options"] = {
        "videos": {"dir_format": "E:/videos/{model_username}"},
        "images": {"dir_format": "{date}"},
        "video": {"file_format": "{media_id}.{ext}"},
        "wall": {"file_format": "{media_id}.{ext}"},
    }
    save()
    lines = naming_check.problems()
    assert (
        'type_options.videos.dir_format "E:/videos/{model_username}" is a full path, but'
        " dir_format is always placed under save_location. Set"
        " type_options.videos.save_location to choose where downloads go"
    ) in lines
    assert any(line.startswith('file_options.date "YYYY/MM" has a folder separator') for line in lines)
    assert "type_options.video isn't a post area, media type or livestreams, so it's never used" in lines
    # a responsetype folder name is a name an entry can match
    assert not any(line.startswith("type_options.wall") for line in lines)

    # livestream folders take the start time, not the date setting
    config["type_options"] = {}
    config["live_options"] = {"dir_format": "{date}"}
    save()
    assert not any(line.startswith("file_options.date") for line in naming_check.problems())


def test_live_names_without_the_start_time_get_it(path_options, tmp_path):
    """Two streams of one creator would get one file: OnlyFans opens it
    with "xb" and fails, Fansly reads the first stream's sidecar"""
    import datetime
    from ofscraper.utils.config import naming_check

    config, save = path_options
    config["live_options"] = {"dir_format": "{model_username}", "file_format": "{model_username}_live"}
    save()
    first, second = (
        placeholder.live_recording_path(tmp_path, "test_creator", datetime.datetime(2024, 5, 1, hour),
                                        site_name="OnlyFans", ext="webm")
        for hour in (1, 2)
    )
    assert first.name == "test_creator_live_20240501_010000.webm"
    assert first != second
    assert any("have no {date} or {timestamp}" in line for line in naming_check.problems())

    # a {date} in the folder keeps them apart too
    config["live_options"]["dir_format"] = "{model_username}/{date}"
    save()
    assert placeholder.live_recording_path(
        tmp_path, "test_creator", datetime.datetime(2024, 5, 1), site_name="OnlyFans", ext="webm"
    ).name == "test_creator_live.webm"
    assert not any("have no {date}" in line for line in naming_check.problems())


@pytest.mark.parametrize("file_format", ["{nope}", "{username[a]}", "{config[file_options][date][x]}"])
def test_a_live_name_that_cant_be_filled_keeps_the_live_folder(path_options, tmp_path, file_format):
    import datetime

    config, save = path_options
    live = tmp_path / "live"
    config["live_options"] = {"save_location": str(live), "file_format": file_format}
    save()
    result = placeholder.live_recording_path(
        tmp_path / "main", "test_creator", datetime.datetime(2024, 5, 1), site_name="OnlyFans", ext="webm")
    assert result == live / "OnlyFans" / "test_creator" / "Livestreams" / "test_creator_20240501_000000_live.webm"


@pytest.mark.parametrize("name", ["message", "Messages", "post", "posts", "Timeline"])
def test_type_options_names_match_their_aliases(path_options, name):
    from ofscraper.utils.config import naming_check

    config, save = path_options
    config["type_options"] = {name: {"dir_format": "here"}}
    save()
    area = "Messages" if name.lower().startswith("message") else "Timeline"
    folder = "Messages" if area == "Messages" else "Posts"
    assert placeholder.media_templates((area, folder, "Images"))[1] == "here"
    assert not any(line.startswith("type_options.") for line in naming_check.problems())


def test_timeline_doesnt_catch_pinned_posts_but_posts_does(path_options):
    """"posts" is the timeline's default folder, which pinned posts are
    saved under too; "timeline" is only the timeline"""
    config, save = path_options
    config["type_options"] = {"timeline": {"dir_format": "wall"}}
    save()
    assert placeholder.media_templates(("Timeline", "Posts", "Images"))[1] == "wall"
    assert placeholder.media_templates(("Pinned", "Posts", "Images"))[1] != "wall"
    config["type_options"] = {"posts": {"dir_format": "wall"}}
    save()
    assert placeholder.media_templates(("Pinned", "Posts", "Images"))[1] == "wall"


def test_type_options_names_for_the_same_type_are_named(path_options):
    from ofscraper.utils.config import naming_check

    config, save = path_options
    config["type_options"] = {"message": {"dir_format": "a"}, "Messages": {"dir_format": "b"}}
    save()
    assert (
        "type_options.message and type_options.Messages name the same type, so only"
        " type_options.Messages is used"
    ) in naming_check.problems()
    assert placeholder.media_templates(("Messages", "Messages", "Images"))[1] == "b"


@pytest.mark.parametrize("dir_format", [
    "/streams/{username}", "D:/streams/{username}", "D:/../streams/{username}",
    "D:../streams/{username}",
])
def test_a_full_path_live_folder_stays_under_the_save_location(path_options, tmp_path, monkeypatch, dir_format):
    import datetime
    import os
    import pathlib

    config, save = path_options
    config["live_options"] = {"save_location": "C:/library", "dir_format": dir_format}
    save()
    if os.name != "nt":
        # Exercise the Windows join on CI hosts that don't have Windows paths.
        monkeypatch.setattr(placeholder, "os", SimpleNamespace(path=ntpath))
        monkeypatch.setattr(placeholder, "pathlib", SimpleNamespace(Path=pathlib.PureWindowsPath))
        monkeypatch.setattr(placeholder, "final_path", lambda path: path)
    result = placeholder.live_recording_path(
        tmp_path, "test_creator", datetime.datetime(2024, 5, 1), site_name="OnlyFans", ext="webm")
    assert result == pathlib.PureWindowsPath("C:/library/streams/test_creator/test_creator_20240501_000000_live.webm")


@pytest.mark.parametrize("site", ["onlyfans", "fansly"])
def test_a_broken_live_template_doesnt_hide_the_other_warnings(path_options, monkeypatch, site):
    from ofscraper.utils.config import naming_check

    config, save = path_options
    config["file_options"]["dir_format"] = "{nope}/x"
    config["live_options"] = {"dir_format": "streams", "file_format": "{date"}
    save()
    current_settings = placeholder.settings.get_settings()
    current_settings.site = site
    monkeypatch.setattr(placeholder.settings, "get_settings", lambda: current_settings)
    lines = []
    monkeypatch.setattr(naming_check.log, "warning", lines.append)
    naming_check.report()
    assert any(line.startswith('file_options.dir_format "{nope}/x"') for line in lines), lines
    assert any(line.startswith('live_options.file_format "{date"') for line in lines)
