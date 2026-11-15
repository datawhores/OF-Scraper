"""A download manager made with a DownloadContext of its own uses only that
context: its semaphore, thread pool, log, attempt counters and totals. These
run managers that way, with no main_globals() call and nothing patched on
the globals module, and check that the process's current context isn't
touched and that two contexts don't mix."""

import asyncio
import contextlib
import logging
from contextlib import closing
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.utils.globals import DownloadContext
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.settings as settings

BODY = b"0123456789" * 50


class _Log(logging.Logger):
    """Records what it's given, with the app's trace and traceback_ levels."""

    def __init__(self):
        super().__init__("test_download_manager_context")
        self.lines = []

    def _record(self, msg, *a, **k):
        self.lines.append(str(msg))

    debug = info = warning = trace = traceback_ = _record

    def log(self, level, msg, *a, **k):
        self.lines.append(str(msg))


class _Reply:
    status = 200

    def __init__(self, body):
        self.body = body
        self.headers = {"content-length": str(len(body)), "content-type": "video/mp4"}

    def iter_chunked(self, size):
        async def gen():
            yield self.body[:200]
            yield self.body[200:]

        return gen()


class _Client:
    """Stands in for the download session: every request gets BODY."""

    def __init__(self):
        self.urls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        self.urls.append(url)
        yield _Reply(BODY)


class _Context:
    """A context of its own; its thread pool is shut down on close."""

    def __init__(self, n=1):
        self.ctx = DownloadContext.for_run(n, log=_Log(), console=object())

    def close(self):
        self.ctx.thread.shutdown()


async def _no_task(*a, **k):
    return None


@pytest.fixture
def store(monkeypatch):
    """What a download needs that isn't the context: settings and the reply
    cache. The globals module isn't touched."""
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            auto_resume=True,
            download_limit=0,
            size_max=0,
            size_min=0,
            skip_download_script=None,
            retry_permanent_skips=False,
            command="download",
        ),
    )
    saved = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: saved.get(key, default))
    monkeypatch.setattr(
        cache, "set", lambda key, value, *a, **k: saved.__setitem__(key, value)
    )
    return saved


def _current_state():
    cur = common_globals.current()
    return {name: getattr(cur, name) for name in common_globals._NAMES}


def _manager(cls, ctx):
    mgr = cls(ctx)
    # the progress bar isn't part of the context
    mgr._add_download_job_task = _no_task
    mgr._remove_download_job_task = _no_task
    return mgr


def _ele(n=1, **kwargs):
    return SimpleNamespace(
        id=n,
        post_id=n,
        username="u",
        filename=f"f{n}",
        url=f"https://example.invalid/{n}.mp4",
        mediatype="Videos",
        skip_script_answers={},
        **kwargs,
    )


def _final(tmp_path):
    path = tmp_path / "f.mp4"
    return SimpleNamespace(filename=path.name, filepath=path, trunicated_filepath=path)


def test_a_manager_made_without_a_context_uses_the_current_one():
    assert md.MainDownloadManager().ctx is common_globals.current()
    ctx = DownloadContext()
    assert ad.AltDownloadManager(ctx).ctx is ctx


def test_main_download_runs_on_its_own_context(tmp_path, store):
    before = _current_state()
    part = tmp_path / "f.part"
    final = _final(tmp_path)
    with closing(_Context()) as own:
        ctx = own.ctx
        mgr = _manager(md.MainDownloadManager, ctx)

        async def go():
            async with ctx.sem:
                ctx.attempt.set(1)
                return await mgr._main_download_sendreq(
                    _Client(), _ele(), SimpleNamespace(tempfilepath=part), placeholderObj=final
                )

        assert asyncio.run(go()) == (len(BODY), part, final)
    assert part.read_bytes() == BODY
    # the reply's data was cached through the context's pool, the file's size
    # added to its total, and the log lines written to its log
    assert store["1_u_headers"]["content-total"] == len(BODY)
    assert ctx.total_bytes == len(BODY)
    assert any("[attempt 1/" in line and "Downloading media with url" in line for line in ctx.log.lines)
    assert any("Download Progress:" in line for line in ctx.log.lines)
    assert any("filename from config f.mp4" in line for line in ctx.log.lines)
    assert ctx.sem._value == 1
    # nothing reached the process's context
    assert _current_state() == before


def test_drm_track_runs_on_its_own_context(tmp_path, store, monkeypatch):
    monkeypatch.setattr(ad.auth_requests, "get_cookies_str", lambda: "")
    before = _current_state()
    part = tmp_path / "track.part"
    ele = _ele(
        mpd="https://example.invalid/v/manifest.mpd",
        hls_header="",
        policy="p",
        keypair="k",
        signature="s",
    )
    item = {
        "name": "track",
        "origname": "track.mp4",
        "type": "audio",
        "total": None,
        "validator": None,
        "before": 0,
    }
    client = _Client()
    with closing(_Context()) as own:
        ctx = own.ctx
        mgr = _manager(ad.AltDownloadManager, ctx)

        async def go():
            # the audio track counts its attempts on attempt2
            ctx.attempt.set(0)
            ctx.attempt2.set(2)
            return await mgr._alt_download_sendreq(
                item, client, ele, SimpleNamespace(tempfilepath=part)
            )

        result = asyncio.run(go())
    assert result["total"] == len(BODY)
    assert part.read_bytes() == BODY
    assert client.urls == ["https://example.invalid/v/track.mp4"]
    assert store["track_1_u_headers"]["content-total"] == len(BODY)
    assert ctx.total_bytes == len(BODY)
    assert any("[attempt 2/" in line and "Downloading media with url" in line for line in ctx.log.lines)
    assert _current_state() == before


def test_two_contexts_keep_their_own_totals_and_semaphores(tmp_path, store):
    """Two runs at once, each with its own context, don't mix their totals
    or wait on each other's semaphore."""

    async def one(ctx, n):
        holder = SimpleNamespace(tempfilepath=tmp_path / f"{n}.part")
        async with ctx.sem:
            ctx.attempt.set(1)
            return await _manager(md.MainDownloadManager, ctx)._main_download_sendreq(
                _Client(), _ele(n), holder, placeholderObj=_final(tmp_path)
            )

    with closing(_Context()) as first, closing(_Context()) as second:
        a, b = first.ctx, second.ctx

        async def go():
            # a's only slot is taken while b downloads: b doesn't wait on it
            await a.sem.acquire()
            try:
                await asyncio.wait_for(one(b, 2), timeout=5)
            finally:
                a.sem.release()
            await one(a, 1)
            await one(a, 3)

        asyncio.run(go())
    assert (a.total_bytes, b.total_bytes) == (2 * len(BODY), len(BODY))
    # each log has only its own run's items
    a_lines, b_lines = "\n".join(a.log.lines), "\n".join(b.log.lines)
    assert "Media:1 " in a_lines and "Media:3 " in a_lines and "Media:2 " not in a_lines
    assert "Media:2 " in b_lines and "Media:1 " not in b_lines
