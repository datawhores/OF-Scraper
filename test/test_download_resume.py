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

A resume sends If-Range with the ETag or Last-Modified of the reply that
started the .part, so a file that changed but kept its size comes back whole
(200) instead of being joined to the old start (#259).
"""

import asyncio
import contextlib
import contextvars
import logging
from types import SimpleNamespace

import pytest
from aiohttp import ClientSession, web
from tenacity import AsyncRetrying, stop_after_attempt

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


def _handler(mode, seen, body=BODY, validator=None, if_ranges=None):
    """validator: the ETag and/or Last-Modified headers the server sends for
    its current file. A Range with an If-Range that isn't one of them gets the
    whole file (200), as RFC 9110 says."""
    size = len(body)
    validator = validator or {}

    async def handler(request):
        rng = request.headers.get("Range")
        seen.append(rng)
        if_range = request.headers.get("If-Range")
        if if_ranges is not None:
            if_ranges.append(if_range)
        if (
            if_range is not None
            and if_range not in validator.values()
            and mode != "ignore-if-range"
        ):
            rng = None
        if not rng or mode == "ignore-range":
            return web.Response(
                status=200, body=body, headers=validator, content_type="video/mp4"
            )
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
        headers = dict(validator)
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


async def _serve(mode, seen, run, body=BODY, validator=None, if_ranges=None):
    app = web.Application()
    app.router.add_get("/f", _handler(mode, seen, body, validator, if_ranges))
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


BODY_SAME_SIZE = bytes((i * 7) % 253 for i in range(T))  # changed, same size
LM = "Wed, 21 Oct 2026 07:28:00 GMT"


def _retry_once(monkeypatch, module):
    monkeypatch.setattr(
        module,
        "download_retry",
        lambda: AsyncRetrying(stop=stop_after_attempt(1), reraise=True),
    )
    monkeypatch.setattr(module, "get_download_retries", lambda: 1)


def _main_download(
    tmp_path, monkeypatch, saved, body=BODY, validator=None, mode="range"
):
    """The whole normal download step, from the reply data saved by the run
    that started the .part (300,000 bytes of BODY) to the finished .part."""
    part = tmp_path / "f.part"
    part.write_bytes(BODY[:300_000])
    _retry_once(monkeypatch, md)
    monkeypatch.setattr(
        common_globals, "attempt", contextvars.ContextVar("a", default=0), raising=False
    )

    class _Placeholder:
        def __init__(self, *a):
            pass

        async def init(self):
            return SimpleNamespace(
                tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4"
            )

    monkeypatch.setattr(md.placeholder, "tempFilePlaceholder", _Placeholder)
    monkeypatch.setattr(md.placeholder, "Placeholders", _Placeholder)
    seen, if_ranges, cached = [], [], []
    mgr = _manager(md.MainDownloadManager, cached)
    mgr._downloadspace = lambda: None

    async def _get_data(ele):
        return saved

    mgr._get_data = _get_data
    ele = SimpleNamespace(url="x", id=1, post_id=1, username="u", filename="f")

    async def run(c):
        return await mgr._main_download_downloader(c, ele)

    total, _, _ = asyncio.run(_serve(mode, seen, run, body, validator, if_ranges))
    return total, part.read_bytes(), seen, if_ranges, cached


def test_main_changed_file_same_size_starts_over(tmp_path, monkeypatch):
    # #259: the file changed but kept its size. The If-Range from the first
    # reply's ETag makes the server send the new file whole, instead of its
    # end being added to the start of the old one.
    saved = {"content-total": T, "content-type": "video/mp4", "validator": '"v1"'}
    total, data, seen, if_ranges, cached = _main_download(
        tmp_path, monkeypatch, saved, BODY_SAME_SIZE, {"ETag": '"v2"'}
    )
    assert seen == ["bytes=300000-"]
    assert if_ranges == ['"v1"']
    assert total == T
    assert data == BODY_SAME_SIZE
    assert [c["validator"] for c in cached] == ['"v2"']


def test_main_unchanged_file_resumes_with_last_modified(tmp_path, monkeypatch):
    # a server with no ETag: Last-Modified goes in If-Range
    saved = {"content-total": T, "content-type": "video/mp4", "validator": LM}
    total, data, seen, if_ranges, cached = _main_download(
        tmp_path, monkeypatch, saved, BODY, {"Last-Modified": LM}
    )
    assert seen == ["bytes=300000-"]
    assert if_ranges == [LM]
    assert total == T
    assert data == BODY
    assert [c["validator"] for c in cached] == [LM]


def test_main_weak_etag_sends_no_if_range(tmp_path, monkeypatch):
    # a weak ETag can't go in If-Range, and a date mustn't go there when the
    # server has an ETag, so nothing is saved or sent
    saved = {"content-total": T, "content-type": "video/mp4", "validator": None}
    total, data, seen, if_ranges, cached = _main_download(
        tmp_path, monkeypatch, saved, BODY, {"ETag": 'W/"v1"', "Last-Modified": LM}
    )
    assert seen == ["bytes=300000-"]
    assert if_ranges == [None]
    assert data == BODY
    assert [c["validator"] for c in cached] == [None]


def test_main_saved_data_without_validator_resumes_as_before(tmp_path, monkeypatch):
    # saved by an older version, or the server sent no ETag or Last-Modified.
    # The 206's ETag isn't saved: the part's start was never checked against it
    saved = {"content-total": T, "content-type": "video/mp4"}
    total, data, seen, if_ranges, cached = _main_download(
        tmp_path, monkeypatch, saved, BODY, {"ETag": '"v1"'}
    )
    assert seen == ["bytes=300000-"]
    assert if_ranges == [None]
    assert total == T
    assert data == BODY
    assert [c["validator"] for c in cached] == [None]


def test_main_server_ignoring_if_range_starts_over(tmp_path, monkeypatch):
    # the server sends the rest of the new file (206) despite If-Range, but
    # its ETag shows the file changed: the part is dropped and the new file
    # downloaded whole, and only then is its ETag saved
    saved = {"content-total": T, "content-type": "video/mp4", "validator": '"v1"'}
    total, data, seen, if_ranges, cached = _main_download(
        tmp_path,
        monkeypatch,
        saved,
        BODY_SAME_SIZE,
        {"ETag": '"v2"'},
        mode="ignore-if-range",
    )
    assert seen == ["bytes=300000-", None]
    assert if_ranges == ['"v1"', None]
    assert total == T
    assert data == BODY_SAME_SIZE
    assert [c["validator"] for c in cached] == ['"v2"']


@pytest.mark.parametrize(
    "mode, requests",
    [
        ("range", ["bytes=300000-"]),
        # a 206 despite If-Range: its ETag shows the change, so start over
        ("ignore-if-range", ["bytes=300000-", None]),
    ],
)
def test_drm_changed_file_same_size_starts_over(tmp_path, monkeypatch, mode, requests):
    part = tmp_path / "v.part"
    part.write_bytes(BODY[:300_000])
    _retry_once(monkeypatch, ad)
    for name in ("attempt", "attempt2"):
        monkeypatch.setattr(
            common_globals, name, contextvars.ContextVar(name, default=0), raising=False
        )
    monkeypatch.setattr(ad, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: "x")
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.auth_requests, "get_cookies_str", lambda: "")

    class _Placeholder:
        def __init__(self, *a):
            pass

        async def init(self):
            return SimpleNamespace(tempfilepath=part, trunicated_filepath=part)

    monkeypatch.setattr(ad.placeholder, "tempFilePlaceholder", _Placeholder)
    seen, if_ranges, cached = [], [], []
    mgr = _manager(ad.AltDownloadManager, cached)
    mgr._downloadspace = lambda: None

    async def _get_data(ele, item):
        return {"content-total": T, "content-type": "video/mp4", "validator": '"v1"'}

    mgr._get_data = _get_data
    ele = SimpleNamespace(mpd="x", hls_header="", id=1, username="u", filename="f")
    item = {"origname": "v", "type": "audio", "name": "v"}

    async def run(c):
        return await mgr._alt_download_downloader(item, c, ele)

    item = asyncio.run(
        _serve(mode, seen, run, BODY_SAME_SIZE, {"ETag": '"v2"'}, if_ranges)
    )
    assert seen == requests
    assert if_ranges == ['"v1"', None][: len(requests)]
    assert item["total"] == T
    assert part.read_bytes() == BODY_SAME_SIZE
    assert [c["validator"] for c in cached] == ['"v2"']


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"etag": '"v1"', "last-modified": LM}, '"v1"'),
        ({"etag": 'W/"v1"', "last-modified": LM}, None),
        ({"etag": 'W/"v1"'}, None),
        ({"last-modified": LM}, LM),
        ({}, None),
    ],
)
def test_validator_prefers_a_strong_etag(headers, expected):
    r = SimpleNamespace(headers=headers)
    assert dm.DownloadManager()._validator(r) == expected


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
