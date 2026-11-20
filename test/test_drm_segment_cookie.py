"""The DRM segment request sends each cookie separately.

The Cookie header joined the CloudFront cookies and the account cookies
with no separator, so the Key-Pair-Id cookie's value ran into "auth_id=..."
and the server got no auth_id cookie. The test runs the DRM downloader's
request step through the real session against a local server and parses
the Cookie header it receives.
"""

import asyncio
import contextvars
import logging
from http.cookies import SimpleCookie
from types import SimpleNamespace

import pytest
from aiohttp import web
from tenacity import stop_after_attempt, wait_none

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.utils.retries as retries
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

BODY = bytes(i % 251 for i in range(10_000))
EXPECTED = {
    "CloudFront-Policy": "policy-value-0001",
    "CloudFront-Signature": "signature-value-0001",
    "CloudFront-Key-Pair-Id": "KEYPAIR0001",
    "auth_id": "424242",
    "sess": "sess-value-0001",
}


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
    monkeypatch.setattr(
        ad,
        "download_retry",
        lambda: retries.download_retry(stop=stop_after_attempt(1), wait=wait_none()),
    )
    monkeypatch.setattr(ad, "get_download_retries", lambda: 1)
    monkeypatch.setattr(ad, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(dm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    # the real get_cookies_str, reading a made-up auth
    monkeypatch.setattr(
        ad.auth_requests.auth_file,
        "read_auth",
        lambda *a, **k: {"auth_id": EXPECTED["auth_id"], "sess": EXPECTED["sess"]},
    )


class _Placeholder:
    part = None

    def __init__(self, *a):
        pass

    async def init(self):
        return SimpleNamespace(
            tempfilepath=self.part, trunicated_filepath=self.part.with_suffix(".mp4")
        )


def _sent_cookie_header(tmp_path, monkeypatch):
    part = tmp_path / "v.part"
    mgr = ad.AltDownloadManager()
    mgr._check_forced_skip = _noop
    mgr._add_download_job_task = _noop
    mgr._remove_download_job_task = _noop
    mgr._total_change_helper = _noop
    mgr._downloadspace = lambda: None
    mgr._get_data = _noop
    mgr._set_data = _noop
    monkeypatch.setattr(
        ad.placeholder, "tempFilePlaceholder", type("P", (_Placeholder,), {"part": part})
    )
    seen = []

    async def handler(request):
        seen.append(request.headers.get("Cookie"))
        return web.Response(body=BODY, content_type="video/mp4")

    async def go():
        app = web.Application()
        app.router.add_get("/{name}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: f"{base}/v")
        # the real hls_header, built from made-up CloudFront values
        signed = SimpleNamespace(
            hls_policy=EXPECTED["CloudFront-Policy"],
            hls_signature=EXPECTED["CloudFront-Signature"],
            hls_keypair=EXPECTED["CloudFront-Key-Pair-Id"],
        )
        ele = SimpleNamespace(
            mpd="x",
            hls_header=Media.hls_header.fget(signed),
            id=1,
            username="u",
            filename="f",
        )
        item = {"origname": "v", "type": "video", "name": "v"}
        try:
            async with sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                return await mgr._alt_download_downloader(item, c, ele)
        finally:
            await runner.cleanup()

    asyncio.run(go())
    assert part.read_bytes() == BODY
    return seen


def test_drm_segment_sends_each_cookie_separately(tmp_path, monkeypatch):
    seen = _sent_cookie_header(tmp_path, monkeypatch)
    assert len(seen) == 1
    parsed = SimpleCookie()
    parsed.load(seen[0])
    assert {k: v.value for k, v in parsed.items()} == EXPECTED
