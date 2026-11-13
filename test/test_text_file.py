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
