"""A whole-file reply to a resume replaces the .part only once data arrives (#271).

A server that ignores Range answers a resume with 200 and the whole file. Both
downloaders deleted the .part, and saved the reply's size and validator, as
soon as that reply came in. If its body then turned out empty (sent chunked,
with no size), the download failed as it should, but the .part and its saved
size were already gone, so the next run started from 0. Now the .part is
replaced, and the new size saved, once the reply's first bytes arrive. Each
test runs a downloader's whole request step, retries included, through the
real session against a local server.
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
OLD = bytes(250 - i % 251 for i in range(T))
HAVE = 30_000
ETAG = '"v2"'


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


def _download(tmp_path, monkeypatch, drm, mode, have=HAVE):
    """Answer every request with the whole file, ignoring Range: `mode` is
    "empty" (chunked, no data), "chunked" (chunked, no size) or "length"
    (with Content-Length). The part holds `have` bytes of an older file.
    Returns (result or exception, Range headers seen, the .part, what was
    cached)."""
    part = tmp_path / ("v.part" if drm else "f.part")
    if have:
        part.write_bytes(OLD[:have])
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

    class _Placeholder:
        def __init__(self, *a):
            pass

        async def init(self):
            return SimpleNamespace(
                tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4"
            )

    for module in (md, ad):
        monkeypatch.setattr(module.placeholder, "tempFilePlaceholder", _Placeholder)
    monkeypatch.setattr(md.placeholder, "Placeholders", _Placeholder)
    seen = []

    async def handler(request):
        seen.append(request.headers.get("Range"))
        if mode == "length":
            return web.Response(
                status=200, body=BODY, content_type="video/mp4", headers={"ETag": ETAG}
            )
        resp = web.StreamResponse(status=200, headers={"ETag": ETAG})
        resp.content_type = "video/mp4"
        resp.enable_chunked_encoding()
        await resp.prepare(request)
        if mode == "chunked":
            await resp.write(BODY)
        await resp.write_eof()
        return resp

    async def download(c, base):
        if drm:
            monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: f"{base}/v")
            ele = SimpleNamespace(mpd="x", hls_header="", id=1, username="u", filename="f")
            item = {"origname": "v", "type": "video", "name": "v"}
            return (await mgr._alt_download_downloader(item, c, ele))["total"]
        ele = SimpleNamespace(url=f"{base}/f", id=1, post_id=1, username="u", filename="f")
        return (await mgr._main_download_downloader(c, ele))[0]

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
def test_empty_full_reply_to_resume_keeps_the_part(tmp_path, monkeypatch, drm):
    # the reply had no data, so the part and its saved size stay for the
    # next run; the retry resumes from the same part too (#268)
    result, seen, part, cached = _download(tmp_path, monkeypatch, drm, "empty")
    assert isinstance(result, Exception)
    assert "no data and no file size" in str(result)
    assert part.read_bytes() == OLD[:HAVE]
    assert seen == ["bytes=30000-", "bytes=30000-"]
    assert cached == []


@RUNS
@pytest.mark.parametrize("mode", ["chunked", "length"])
def test_full_reply_to_resume_replaces_the_part(tmp_path, monkeypatch, drm, mode):
    # data arrived: the part is written again from byte 0, not appended to,
    # and the new reply's size and validator are saved
    total, seen, part, cached = _download(tmp_path, monkeypatch, drm, mode)
    assert total == T
    assert part.read_bytes() == BODY
    assert seen == ["bytes=30000-"]
    assert cached == [
        {
            "content-total": None if mode == "chunked" else T,
            "content-type": "video/mp4",
            "validator": ETAG,
        }
    ]


@RUNS
@pytest.mark.parametrize("mode", ["chunked", "length"])
def test_fresh_download_is_unchanged(tmp_path, monkeypatch, drm, mode):
    total, seen, part, cached = _download(tmp_path, monkeypatch, drm, mode, have=0)
    assert total == T
    assert part.read_bytes() == BODY
    assert seen == [None]
    assert len(cached) == 1


@RUNS
def test_empty_fresh_download_fails_without_a_part(tmp_path, monkeypatch, drm):
    result, seen, part, cached = _download(tmp_path, monkeypatch, drm, "empty", have=0)
    assert isinstance(result, Exception)
    assert "no data and no file size" in str(result)
    assert seen == [None, None]
    assert cached == []
    assert not part.exists()
