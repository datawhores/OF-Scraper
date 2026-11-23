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
