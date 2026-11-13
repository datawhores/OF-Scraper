"""A retried error while resuming keeps the .part (#268).

Both downloaders deleted the .part before every retry, so an error the
session raises and the downloader retries (403, 429, 5xx) during a resume
made the retry start from 0, and if the retry failed too, the next run
started from 0 as well. Each test runs a downloader's whole request step,
retries included, through the real session against a local server.
"""

import asyncio
import contextvars
import logging
from types import SimpleNamespace

import pytest
from aiohttp import ClientResponseError, web
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
HAVE = 30_000


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


def _download(tmp_path, monkeypatch, drm, errors):
    """Resume from HAVE bytes; the first `errors` requests get a 503, the
    rest the file (206 to a Range). Returns (result or exception, Range
    headers seen, the .part)."""
    part = tmp_path / ("v.part" if drm else "f.part")
    part.write_bytes(BODY[:HAVE])
    saved = {"content-total": T, "content-type": "video/mp4"}
    mgr = (ad.AltDownloadManager if drm else md.MainDownloadManager)()
    mgr._check_forced_skip = _noop
    mgr._add_download_job_task = _noop
    mgr._remove_download_job_task = _noop
    mgr._total_change_helper = _noop
    mgr._downloadspace = lambda: None

    async def _get_data(*args):
        return saved

    mgr._get_data, mgr._set_data = _get_data, _noop
    placeholder = type("P", (_Placeholder,), {"part": part})
    for module in (md, ad):
        monkeypatch.setattr(module.placeholder, "tempFilePlaceholder", placeholder)
    monkeypatch.setattr(md.placeholder, "Placeholders", placeholder)
    seen = []

    async def handler(request):
        rng = request.headers.get("Range")
        seen.append(rng)
        if len(seen) <= errors:
            return web.Response(status=503, text="busy")
        if not rng:
            return web.Response(status=200, body=BODY, content_type="video/mp4")
        start = int(rng.split("=")[1].split("-")[0])
        return web.Response(
            status=206,
            body=BODY[start:],
            headers={"Content-Range": f"bytes {start}-{T - 1}/{T}"},
            content_type="video/mp4",
        )

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

    return asyncio.run(go()), seen, part


RUNS = pytest.mark.parametrize("drm", [False, True], ids=["normal", "drm"])


@RUNS
def test_retry_resumes_the_part(tmp_path, monkeypatch, drm):
    result, seen, part = _download(tmp_path, monkeypatch, drm, errors=1)
    assert not isinstance(result, Exception)
    # the retry asks for the rest, not the whole file
    assert seen == [f"bytes={HAVE}-", f"bytes={HAVE}-"]
    assert part.read_bytes() == BODY


@RUNS
def test_failed_retries_keep_the_part(tmp_path, monkeypatch, drm):
    # the next run resumes from what was there
    result, seen, part = _download(tmp_path, monkeypatch, drm, errors=2)
    assert isinstance(result, ClientResponseError) and result.status == 503
    assert seen == [f"bytes={HAVE}-", f"bytes={HAVE}-"]
    assert part.read_bytes() == BODY[:HAVE]
