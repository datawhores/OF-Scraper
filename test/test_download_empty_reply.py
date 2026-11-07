"""An empty reply to a media download is a failed download (#267).

A 200 with Content-Length: 0 gave the normal downloader a size of 0, which
means "skipped": the item was marked as downloaded with no file, and on a
resume the .part was deleted first. The DRM downloader failed, but also
deleted the .part on a resume. Each test runs a downloader's whole request
step, retries included, through the real session against a local server.
"""

import asyncio
import contextvars
import logging
from types import SimpleNamespace

import pytest
from aiohttp import web
from tenacity import stop_after_attempt, wait_none

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.utils.retries as retries
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

T = 100_000
BODY = bytes(i % 251 for i in range(T))


async def _noop(*args, **kwargs):
    return None


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            auto_resume=True,
            download_limit=0,
            command="download",
            ssl_verify="false",
            cached_disabled=True,
        ),
    )
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)
    for name in ("attempt", "attempt2"):
        monkeypatch.setattr(
            common_globals, name, contextvars.ContextVar(name, default=0), raising=False
        )
    for module in (md, ad):
        monkeypatch.setattr(
            module,
            "download_retry",
            lambda: retries.download_retry(stop=stop_after_attempt(2), wait=wait_none()),
        )
        monkeypatch.setattr(module, "get_download_retries", lambda: 2)
        monkeypatch.setattr(module, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(md.common_logs, "path_to_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(md.common_logs, "get_medialog", lambda ele: "")
    monkeypatch.setattr(dm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.auth_requests, "get_cookies_str", lambda: "")


class _Placeholder:
    part = None

    def __init__(self, *a):
        pass

    async def init(self):
        return SimpleNamespace(
            tempfilepath=self.part, trunicated_filepath=self.part.with_suffix(".mp4")
        )


def _download(tmp_path, monkeypatch, drm, have, status=200):
    """Answer every request with an empty `status` reply. Returns (result or
    exception, Range headers seen, the .part, what was cached)."""
    part = tmp_path / ("v.part" if drm else "f.part")
    if have:
        part.write_bytes(BODY[:have])
    saved = {"content-total": T, "content-type": "video/mp4"} if have else None
    cached = []
    mgr = (ad.AltDownloadManager if drm else md.MainDownloadManager)()
    mgr._check_forced_skip = _noop
    mgr._add_download_job_task = _noop
    mgr._remove_download_job_task = _noop
    mgr._total_change_helper = _noop
    mgr._downloadspace = lambda: None

    async def _get_data(*args):
        return saved

    async def _set_data(*args):
        cached.append(args[-1])

    mgr._get_data, mgr._set_data = _get_data, _set_data
    placeholder = type("P", (_Placeholder,), {"part": part})
    for module in (md, ad):
        monkeypatch.setattr(module.placeholder, "tempFilePlaceholder", placeholder)
    monkeypatch.setattr(md.placeholder, "Placeholders", placeholder)
    seen = []

    async def handler(request):
        seen.append(request.headers.get("Range"))
        return web.Response(status=status, body=b"", content_type="video/mp4")

    async def download(c, base):
        if drm:
            monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: f"{base}/v")
            ele = SimpleNamespace(mpd="x", hls_header="", id=1, username="u", filename="f")
            item = {"origname": "v", "type": "video", "name": "v"}
            return await mgr._alt_download_downloader(item, c, ele)
        ele = SimpleNamespace(url=f"{base}/f", id=1, post_id=1, username="u", filename="f")
        return await mgr._main_download_downloader(c, ele)

    async def go():
        app = web.Application()
        app.router.add_get("/{name}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        try:
            async with sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                try:
                    return await download(c, base)
                except Exception as E:
                    return E
        finally:
            await runner.cleanup()

    return asyncio.run(go()), seen, part, cached


RUNS = pytest.mark.parametrize("drm", [False, True], ids=["normal", "drm"])


@RUNS
@pytest.mark.parametrize("status", [200, 204])
def test_empty_reply_fails(tmp_path, monkeypatch, drm, status):
    # not a size of 0, which reads as "skipped" and marks the item downloaded
    result, seen, part, cached = _download(tmp_path, monkeypatch, drm, 0, status)
    assert isinstance(result, dm.ErrorReply)
    assert "empty reply" in str(result)
    assert seen == [None]
    assert cached == []
    assert not part.exists()


@RUNS
def test_empty_reply_to_resume_keeps_the_part(tmp_path, monkeypatch, drm):
    result, seen, part, cached = _download(tmp_path, monkeypatch, drm, 30_000)
    assert isinstance(result, dm.ErrorReply)
    assert part.read_bytes() == BODY[:30_000]
    assert seen == ["bytes=30000-"]
    assert cached == []
