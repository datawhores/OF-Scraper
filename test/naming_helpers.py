"""File names and text files for one post, built by the real placeholder
classes from real settings: command-line options over an empty config.json.

    from naming_helpers import make_post, naming, text_files  # noqa: F401
"""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.settings as settings
from ofscraper.utils.args.main import AutoDotDict
from ofscraper.utils.args.parse.commands.main import program


def make_post(caption, media=1, post_id=8):
    """A post dated 2026-10-31 with `media` images, named pic0.jpg, pic1.jpg, ..."""
    raw = {"id": post_id, "text": caption, "price": 0, "isOpened": True,
           "responseType": "post", "postedAt": "2026-10-31T12:00:00+00:00",
           "media": [{"id": 70 + n, "type": "photo", "canView": True,
                      "files": {"full": {"url": f"https://example.invalid/pic{n}.jpg"}}}
                     for n in range(media)]}
    return posts_.Post(raw, 1, "u", "timeline")


def text_files(tmp_path):
    """The text files saved under the test's save location: name -> content."""
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in (tmp_path / "data").rglob("*.txt")
    }


async def _none(*args, **kwargs):
    return None


@pytest.fixture
def naming(monkeypatch, tmp_path):
    """Returns names(file_format, caption, *options, media=1, text=True): the
    text file's name (None with text=False) and each media file's name, for
    one post with that caption. The options are command-line options, e.g.
    "--text-type", "word". Files are saved under tmp_path/"data", in a folder
    named by the post's date."""
    quiet = SimpleNamespace(
        trace=_nothing, debug=_nothing, info=_nothing, warning=_nothing
    )
    monkeypatch.setattr(placeholder, "log", quiet)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(
        placeholder.profile_data, "get_active_profile", lambda: "main_profile"
    )
    monkeypatch.setattr(
        placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg"
    )
    monkeypatch.setattr(
        placeholder.common_paths,
        "get_save_location",
        lambda *a, **k: str(tmp_path / "data"),
    )
    monkeypatch.setattr(placeholder.config_file, "open_config", lambda: {})
    monkeypatch.setattr(
        placeholder.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(get_model=lambda _u: None)),
    )
    monkeypatch.setattr(placeholder, "naming_script", _none)
    monkeypatch.setattr(placeholder.data, "get_date", lambda *a, **k: "YYYY-MM-DD")
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: "{date}")

    def names(file_format, caption, *options, media=1, text=True):
        params, _ = program.main(
            args=list(options), standalone_mode=False, prog_name="OF-Scraper"
        )
        args = AutoDotDict(params)
        args.command = "OF-Scraper"
        monkeypatch.setattr(settings.read_args, "retriveArgs", lambda *a, **k: args)
        monkeypatch.setattr(settings, "get_args", lambda *a, **k: args)
        merged = settings.merged_settings()
        monkeypatch.setattr(settings, "get_settings", lambda *a, **k: merged)
        monkeypatch.setattr(
            placeholder.data, "get_fileformat", lambda *a, **k: file_format
        )
        post = make_post(caption, media)
        if text:
            text = asyncio.run(placeholder.Textholders(post, "txt").createfilename())
        return (text or None), [
            asyncio.run(placeholder.Placeholders(item, "jpg").createfilename())
            for item in post.all_media
        ]

    return names


def _nothing(*args, **kwargs):
    pass
