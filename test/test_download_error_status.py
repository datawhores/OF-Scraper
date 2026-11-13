"""An error reply to a media download is a failed download (#261).

The session raises for most error statuses but hands a 404 back to the
caller, and both downloaders used to write its body, a short error page, as
the media file: the item was then moved into place and marked as downloaded,
so it was never fetched again. Each test runs a downloader's whole request
step, retries included, through the real session against a local server.
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
PAGE = b"<html><body>404 Not Found</body></html>"


async def _noop(*args, **kwargs):
    return None


class _Log:
    """The downloaders' log, which also has trace and traceback_."""

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
        # two tries, no wait, with the real rule for what is retried
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


def _manager(cls, saved, cached):
    mgr = cls()
    mgr._check_forced_skip = _noop
    mgr._add_download_job_task = _noop
    mgr._remove_download_job_task = _noop
    mgr._total_change_helper = _noop
    mgr._downloadspace = lambda: None

    async def _get_data(*args):
        return saved

    async def _set_data(*args):
        cached.append(args[-1])

    mgr._get_data = _get_data
    mgr._set_data = _set_data
    return mgr


def _placeholder(tmp_path, part):
    class _Placeholder:
        def __init__(self, *a):
            pass

        async def init(self):
            return SimpleNamespace(
                tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4"
            )

    return _Placeholder


def _run(status, download):
    """Serve `status` with an error page to every request; return (result or
    exception, Range headers seen)."""
    seen = []

    async def handler(request):
        seen.append(request.headers.get("Range"))
        return web.Response(status=status, body=PAGE, content_type="text/html")

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
                    return await download(c, base), seen
                except Exception as E:
                    return E, seen
        finally:
            await runner.cleanup()

    return asyncio.run(go())


def _main(tmp_path, monkeypatch, status, have):
    part = tmp_path / "f.part"
    if have:
        part.write_bytes(BODY[:have])
    saved = {"content-total": T, "content-type": "video/mp4"} if have else None
    cached = []
    mgr = _manager(md.MainDownloadManager, saved, cached)
    ph = _placeholder(tmp_path, part)
    monkeypatch.setattr(md.placeholder, "tempFilePlaceholder", ph)
    monkeypatch.setattr(md.placeholder, "Placeholders", ph)

    async def download(c, base):
        ele = SimpleNamespace(
            url=f"{base}/f", id=1, post_id=1, username="u", filename="f"
        )
        return await mgr._main_download_downloader(c, ele)

    result, seen = _run(status, download)
    return result, seen, part, cached


def _drm(tmp_path, monkeypatch, status, have):
    part = tmp_path / "v.part"
    if have:
        part.write_bytes(BODY[:have])
    saved = {"content-total": T, "content-type": "video/mp4"} if have else None
    cached = []
    mgr = _manager(ad.AltDownloadManager, saved, cached)
    monkeypatch.setattr(
        ad.placeholder, "tempFilePlaceholder", _placeholder(tmp_path, part)
    )

    async def download(c, base):
        monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: f"{base}/v")
        ele = SimpleNamespace(mpd="x", hls_header="", id=1, username="u", filename="f")
        item = {"origname": "v", "type": "video", "name": "v"}
        return await mgr._alt_download_downloader(item, c, ele)

    result, seen = _run(status, download)
    return result, seen, part, cached


@pytest.mark.parametrize("run", [_main, _drm], ids=["normal", "drm"])
def test_404_fresh_download_fails(tmp_path, monkeypatch, run):
    result, seen, part, cached = run(tmp_path, monkeypatch, 404, 0)
    # the error page isn't written or returned as the file
    assert not part.exists()
    assert cached == []
    assert isinstance(result, Exception) and "404" in str(result)
    assert seen == [None]  # not retried in this run; the next run tries again
    assert isinstance(result, dm.ErrorReply)


@pytest.mark.parametrize("run", [_main, _drm], ids=["normal", "drm"])
def test_404_resume_keeps_the_part(tmp_path, monkeypatch, run):
    result, seen, part, cached = run(tmp_path, monkeypatch, 404, 30_000)
    assert part.exists() and part.read_bytes() == BODY[:30_000]
    assert cached == []
    assert isinstance(result, Exception) and "404" in str(result)
    assert seen == ["bytes=30000-"]
    assert isinstance(result, dm.ErrorReply)


@pytest.mark.parametrize("run", [_main, _drm], ids=["normal", "drm"])
def test_403_still_fails_and_is_retried(tmp_path, monkeypatch, run):
    # an expired link: the session raises, and the downloader retries as before
    result, seen, part, _ = run(tmp_path, monkeypatch, 403, 0)
    assert isinstance(result, ClientResponseError)
    assert result.status == 403
    assert seen == [None, None]
    assert not part.exists()
