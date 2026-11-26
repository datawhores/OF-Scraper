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
# From test_text_file.py
# ----------------------------------------------------------------------

import asyncio
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
