"""Resuming a download from a leftover .part file (#244).

Each test runs a downloader's request step against a local server, with the
first R bytes of a file already in the .part. The normal downloader used to
take the 206 reply's Content-Length (only the missing bytes) as the size of
the whole file: with more than half on disk it deleted the .part, wrote only
the end of the file and passed the size check. The DRM downloader built the
Range header and then replaced it with only the Cookie, so it appended the
whole file after the partial data and downloaded it again.

A reply that doesn't fit the .part (a file of another size than the one the
.part was started from, no size at all, or a 416) deletes the .part and
downloads the file again from the start.
"""

import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest
from aiohttp import ClientSession, web

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

T = 1_000_000
BODY = bytes(i % 251 for i in range(T))


BODY_NEW = bytes((i * 7) % 253 for i in range(1_200_000))  # the file, changed


def _handler(mode, seen, body=BODY):
    size = len(body)

    async def handler(request):
        rng = request.headers.get("Range")
        seen.append(rng)
        if not rng or mode == "ignore-range":
            return web.Response(status=200, body=body, content_type="video/mp4")
        start, end = rng.split("=")[1].split("-")
        start = int(start)
        if start >= size:
            return web.Response(
                status=416, headers={"Content-Range": f"bytes */{size}"}
            )
        end = min(int(end) if end else size - 1, size - 1)
        if mode == "no-size":
            # chunked, and no Content-Range: nothing says how big the file is
            resp = web.StreamResponse(status=206)
            resp.content_type = "video/mp4"
            resp.enable_chunked_encoding()
            await resp.prepare(request)
            await resp.write(body[start : end + 1])
            await resp.write_eof()
            return resp
        headers = {}
        if mode != "no-content-range":
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return web.Response(
            status=206,
            body=body[start : end + 1],
            headers=headers,
            content_type="video/mp4",
        )

    return handler


class _Client:
    """Stands in for the download session: one plain aiohttp GET."""

    def __init__(self, session, url):
        self.session, self.url = session, url

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, headers=None, **kwargs):
        r = await self.session.get(self.url, headers=headers or {})
        r.iter_chunked = r.content.iter_chunked
        try:
            yield r
        finally:
            r.release()


async def _noop(*args, **kwargs):
    return None


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            auto_resume=True, download_limit=0, command="download"
        ),
    )
    monkeypatch.setattr(common_globals, "log", logging.getLogger("test"), raising=False)
    monkeypatch.setattr(common_globals, "attempt", SimpleNamespace(get=lambda *a: 1), raising=False)
    monkeypatch.setattr(md, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(md.common_logs, "path_to_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(md.common_logs, "get_medialog", lambda ele: "")
    monkeypatch.setattr(dm, "get_medialog", lambda ele: "")


def _manager(module_class, cached):
    mgr = module_class()
    mgr._check_forced_skip = _noop
    mgr._add_download_job_task = _noop
    mgr._remove_download_job_task = _noop
    mgr._total_change_helper = _noop

    async def _set_data(*args):
        cached.append(args[-1])

    mgr._set_data = _set_data
    return mgr


async def _serve(mode, seen, run, body=BODY):
    app = web.Application()
    app.router.add_get("/f", _handler(mode, seen, body))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        async with ClientSession() as session:
            return await run(_Client(session, f"http://127.0.0.1:{port}/f"))
    finally:
        await runner.cleanup()


def _main_resume(
    tmp_path, have, mode="range", cached_total=T, part_data=None, body=BODY
):
    part = tmp_path / "f.part"
    part_data = BODY[:have] if part_data is None else part_data
    if part_data:
        part.write_bytes(part_data)
    seen, cached = [], []
    mgr = _manager(md.MainDownloadManager, cached)
    tmp = SimpleNamespace(tempfilepath=part)
    ph = SimpleNamespace(trunicated_filepath=tmp_path / "f.mp4")
    ele = SimpleNamespace(url="x", id=1, username="u", filename="f")

    async def run(c):
        return await mgr._main_download_sendreq(
            c, ele, tmp, placeholderObj=ph, total=cached_total
        )

    total, _, _ = asyncio.run(_serve(mode, seen, run, body))
    return total, part.read_bytes(), seen, cached


@pytest.mark.parametrize("have", [300_000, 700_000])
def test_main_resume_appends_missing_bytes(tmp_path, have):
    total, data, seen, cached = _main_resume(tmp_path, have)
    assert seen == [f"bytes={have}-"]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_main_resume_without_content_range(tmp_path):
    total, data, _, cached = _main_resume(tmp_path, 700_000, mode="no-content-range")
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


@pytest.mark.parametrize("have", [300_000, 700_000])
def test_main_server_ignores_range_restarts(tmp_path, have):
    total, data, seen, cached = _main_resume(tmp_path, have, mode="ignore-range")
    assert seen == [f"bytes={have}-"]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_main_part_without_cached_size_restarts(tmp_path):
    # no cached size means no Range header, so the server sends everything
    total, data, seen, _ = _main_resume(tmp_path, 300_000, cached_total=None)
    assert seen == [None]
    assert total == T
    assert data == BODY


def test_main_fresh_download(tmp_path):
    total, data, seen, cached = _main_resume(tmp_path, 0, cached_total=None)
    assert seen == [None]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_main_part_from_older_version_is_not_appended(tmp_path):
    # An older version, resuming with 700,000 of 1,000,000 bytes on disk,
    # deleted the .part, saved 300,000 as the size and started writing only the
    # end of the file. Stopped mid-write, the .part holds bytes from the middle.
    total, data, seen, cached = _main_resume(
        tmp_path, 0, cached_total=300_000, part_data=BODY[700_000:800_000]
    )
    assert seen == ["bytes=100000-", None]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_main_file_changed_size_restarts(tmp_path):
    # the .part is the start of the old 1,000,000-byte file; the server now
    # has a 1,200,000-byte file
    total, data, seen, cached = _main_resume(tmp_path, 300_000, body=BODY_NEW)
    assert seen == ["bytes=300000-", None]
    assert total == len(BODY_NEW)
    assert data == BODY_NEW
    assert [c["content-total"] for c in cached] == [len(BODY_NEW)]


def test_main_206_without_size_restarts(tmp_path):
    total, data, seen, cached = _main_resume(tmp_path, 700_000, mode="no-size")
    assert seen == ["bytes=700000-", None]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_main_416_restarts(tmp_path):
    # the whole file is on disk but the saved size is larger, so the server
    # has nothing to send from byte 1,000,000 on and answers 416
    total, data, seen, cached = _main_resume(tmp_path, T, cached_total=1_500_000)
    assert seen == [f"bytes={T}-", None]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def _alt_resume(
    tmp_path, monkeypatch, have, mode="range", cached_total=T, kind="video", body=BODY
):
    monkeypatch.setattr(
        common_globals, "attempt2", SimpleNamespace(get=lambda *a: 1), raising=False
    )
    monkeypatch.setattr(ad, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: "x")
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.auth_requests, "get_cookies_str", lambda: "")
    part = tmp_path / "v.part"
    if have:
        part.write_bytes(BODY[:have])
    seen, cached = [], []
    mgr = _manager(ad.AltDownloadManager, cached)
    ph = SimpleNamespace(tempfilepath=part, trunicated_filepath=part)
    ele = SimpleNamespace(mpd="x", hls_header="", id=1, username="u", filename="f")
    item = {"origname": "v", "total": cached_total, "type": kind, "name": "v"}

    async def run(c):
        return await mgr._alt_download_sendreq(item, c, ele, ph)

    item = asyncio.run(_serve(mode, seen, run, body))
    return item["total"], part.read_bytes(), seen, cached


@pytest.mark.parametrize("have", [300_000, 700_000])
def test_drm_resume_appends_missing_bytes(tmp_path, monkeypatch, have):
    total, data, seen, cached = _alt_resume(tmp_path, monkeypatch, have)
    assert seen == [f"bytes={have}-"]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


@pytest.mark.parametrize("have", [300_000, 700_000])
def test_drm_server_ignores_range_restarts(tmp_path, monkeypatch, have):
    total, data, seen, cached = _alt_resume(
        tmp_path, monkeypatch, have, mode="ignore-range"
    )
    assert seen == [f"bytes={have}-"]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_drm_fresh_download(tmp_path, monkeypatch):
    total, data, seen, cached = _alt_resume(tmp_path, monkeypatch, 0, cached_total=None)
    assert seen == [None]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def test_drm_audio_file_changed_size_restarts(tmp_path, monkeypatch):
    # the audio .part is the start of the old 1,000,000-byte track; the server
    # now has a 1,200,000-byte track
    total, data, seen, cached = _alt_resume(
        tmp_path, monkeypatch, 300_000, kind="audio", body=BODY_NEW
    )
    assert seen == ["bytes=300000-", None]
    assert total == len(BODY_NEW)
    assert data == BODY_NEW
    assert [c["content-total"] for c in cached] == [len(BODY_NEW)]


def test_drm_416_restarts(tmp_path, monkeypatch):
    total, data, seen, cached = _alt_resume(
        tmp_path, monkeypatch, T, cached_total=1_500_000
    )
    assert seen == [f"bytes={T}-", None]
    assert total == T
    assert data == BODY
    assert [c["content-total"] for c in cached] == [T]


def _session_get(monkeypatch, headers):
    """One request through the real session (5 tries, no wait) to a server
    that answers 416 to everything. Returns (status or exception, requests)."""
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(ssl_verify="false", cached_disabled=True),
    )
    seen = []

    async def handler(request):
        seen.append(request.headers.get("Range"))
        return web.Response(status=416, headers={"Content-Range": f"bytes */{T}"})

    async def go():
        app = web.Application()
        app.router.add_get("/f", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/f"
        try:
            async with sessionManager(
                retries=5, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                try:
                    async with c.requests_async(url=url, headers=headers) as r:
                        return r.status, seen
                except Exception as E:
                    return E, seen
        finally:
            await runner.cleanup()

    return asyncio.run(go())


def test_session_hands_416_to_a_ranged_request(monkeypatch):
    # not retried as an error: the downloader handles it
    status, seen = _session_get(monkeypatch, {"Range": f"bytes={T}-"})
    assert status == 416
    assert seen == [f"bytes={T}-"]


def test_session_still_retries_416_without_range(monkeypatch):
    status, seen = _session_get(monkeypatch, {})
    assert isinstance(status, Exception)
    assert len(seen) == 5


def test_mismatched_content_range_is_rejected():
    r = SimpleNamespace(
        status=206,
        headers={"content-length": "10", "content-range": "bytes 0-9/100"},
    )
    with pytest.raises(Exception, match="bytes from 50"):
        dm.DownloadManager()._full_size_from_reply(r, 50, "unused")
