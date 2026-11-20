"""Debug logs don't show a signed link's query.

The session logged the whole link of a failed request ("failed: ...") and of
each retry ("Request failed for ...", "attempt: N for ..."). Both
downloaders logged the error text and the traceback, and an aiohttp error's
text holds the whole link. A DRM link gets its Policy, Signature and
Key-Pair-Id as separate params, so its query starts with ?Policy=, which the
log filter didn't match: it only knew &Policy=.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager
from ofscraper.utils.logs.classes.classes import SensitiveFormatter
import ofscraper.utils.logs.utils.sensitive as sensitive
from test.test_download_error_status import _manager, _placeholder, _run, _setup  # noqa: F401
from test.test_session_request_retry_args import server  # noqa: F401

FILE = "1920x1080_abcdef0123"
POLICY, SIGNATURE, KEY_PAIR = "eyJTdGF0ZW1lbnQ", "Zx~ab-cd_ef", "K1ABCDEF"
SIGNING = {"Policy": POLICY, "Signature": SIGNATURE, "Key-Pair-Id": KEY_PAIR}
QUERY = f"Tag=2&u=12345&Policy={POLICY}&Signature={SIGNATURE}&Key-Pair-Id={KEY_PAIR}"
SECRETS = [POLICY, SIGNATURE, KEY_PAIR, "u=12345"]


class _Log:
    """Keeps every line, whatever the level."""

    def __init__(self):
        self.lines = []

    def __getattr__(self, name):
        return lambda msg="", *a, **k: self.lines.append(str(msg))


def _assert_hidden(text):
    assert "{hidden}" in text
    for secret in SECRETS:
        assert secret not in text


@pytest.mark.parametrize("separate", [False, True], ids=["in-link", "params"])
@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_session_failed_and_retry_lines_hide_the_query(server, use_async, separate):  # noqa: F811
    url, params = (server.url, SIGNING) if separate else (f"{server.url}?{QUERY}", None)
    log = _Log()

    async def go():
        async with sessionManager(retries=2, wait_min=0, wait_max=0, log=log) as c:
            async with c.requests_async(url=url, params=params):
                pass

    with pytest.raises(Exception):
        if use_async:
            asyncio.run(go())
        else:
            with sessionManager(retries=2, wait_min=0, wait_max=0, log=log) as c:
                with c.requests(url, params=params):
                    pass
    assert server.calls == 2
    text = "\n".join(log.lines)
    assert "failed:" in text
    assert ("Request failed for" if use_async else "attempt: 2") in text
    _assert_hidden(text)


def test_filter_hides_a_query_that_starts_with_policy():
    # a DRM segment's link, its signature sent as separate params
    line = SensitiveFormatter()._filter(
        f"failed: https://cdn3.onlyfans.com/dash/files/a/b/{FILE}.mp4?"
        f"Policy={POLICY}&Signature={SIGNATURE}&Key-Pair-Id={KEY_PAIR}"
    )
    assert "?Policy={hidden}&Signature={hidden}&Key-Pair-Id={hidden}" in line
    for name in ("Signature", "Key-Pair-Id"):
        first = SensitiveFormatter()._filter(f"x.mp4?{name}=abc123&Tag=2")
        assert first == f"x.mp4?{name}={{hidden}}&Tag=2"


def test_hide_link():
    link = f"https://cdn3.onlyfans.com/dash/files/a/ab/abcdef123/{FILE}.mp4?{QUERY}"
    assert sensitive.hide_link(link) == (
        f"https://cdn3.onlyfans.com/dash/files/a/ab/abcdef123/{FILE}.mp4?{{hidden}}"
    )
    assert sensitive.hide_link(link, hide_path=True) == (
        "https://cdn3.onlyfans.com/dash/files/a/ab/{hidden}/{hidden}.mp4?{hidden}"
    )
    # the site's own name isn't part of the path
    api = "https://onlyfans.com/api2/v2/subscriptions/count"
    assert sensitive.hide_link(api) == api
    assert sensitive.hide_link(api, hide_path=True) == "https://onlyfans.com/api2/v2/{hidden}/count"


def _download_main(tmp_path, monkeypatch):
    part = tmp_path / "f.part"
    mgr = _manager(md.MainDownloadManager, None, [])
    ph = _placeholder(tmp_path, part)
    monkeypatch.setattr(md.placeholder, "tempFilePlaceholder", ph)
    monkeypatch.setattr(md.placeholder, "Placeholders", ph)

    async def download(c, base):
        ele = SimpleNamespace(
            url=f"{base}/{FILE}.mp4?{QUERY}", id=1, post_id=1, username="u", filename=FILE
        )
        return await mgr._main_download_downloader(c, ele)

    return download


def _download_drm(tmp_path, monkeypatch):
    part = tmp_path / "v.part"
    mgr = _manager(ad.AltDownloadManager, None, [])
    monkeypatch.setattr(ad.placeholder, "tempFilePlaceholder", _placeholder(tmp_path, part))
    # sent as separate params, as get_alt_params gives them
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: SIGNING)

    async def download(c, base):
        monkeypatch.setattr(ad, "_mpd_segment_url", lambda mpd, name: f"{base}/{FILE}.mp4")
        ele = SimpleNamespace(mpd="x", hls_header="", id=1, username="u", filename="f")
        item = {"origname": "v", "type": "video", "name": "v"}
        return await mgr._alt_download_downloader(item, c, ele)

    return download


@pytest.mark.parametrize("make", [_download_main, _download_drm], ids=["normal", "drm"])
def test_download_error_text_hides_the_link(tmp_path, monkeypatch, caplog, make):
    log = _Log()
    monkeypatch.setattr(common_globals, "log", log, raising=False)
    tracebacks = []
    monkeypatch.setattr(log, "traceback_", lambda msg, *a, **k: tracebacks.append(msg), raising=False)
    with caplog.at_level(logging.DEBUG, logger="test"):
        result, _ = _run(403, make(tmp_path, monkeypatch))
    # the aiohttp error's own text has the whole link
    assert POLICY in str(result)
    assert tracebacks and any("403" in line for line in tracebacks)
    # the downloader's lines hide the file's name too
    own = tracebacks if make is _download_main else tracebacks + log.lines
    _assert_hidden("\n".join(own))
    assert FILE not in "\n".join(own)
    # the session's "failed:" lines
    session = "\n".join(r.getMessage() for r in caplog.records)
    assert "failed:" in session
    _assert_hidden(session)
