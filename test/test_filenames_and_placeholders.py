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
