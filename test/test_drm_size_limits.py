"""DRM size limits are checked on the whole video, audio + video (#316).

A DRM video downloads as two tracks. The limits were checked on each track's
size on its own, so with a minimum size the small audio track was "under
size min" for almost every video. The skip changed the item's mediatype,
which made its manifest URL None, so the video track and every retry failed
and the item was counted as failed instead of skipped.

Each test runs one DRM item through run.py's consumer (the counters), the
real AltDownloadManager and session, against a local server that serves the
two tracks. Decrypting and merging are stubbed out: they come after the
size decision.
"""

import asyncio
import contextvars
import logging
from types import SimpleNamespace

import pytest
from aiohttp import web
from tenacity import stop_after_attempt, wait_none

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.run as run
import ofscraper.commands.scraper.actions.download.utils.retries as retries
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

AUDIO = bytes(i % 251 for i in range(1_000))
VIDEO = bytes(i % 241 for i in range(5_000))
WHOLE = len(AUDIO) + len(VIDEO)
TRACKS = {"audio.mp4": AUDIO, "video.mp4": VIDEO}


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


async def _noop(*args, **kwargs):
    return None


class _DrmMedia(Media):
    """A DRM video whose two tracks come from the MPD."""

    @property
    def mpd_audio(self):
        return self._track("audio")

    @property
    def mpd_video(self):
        return self._track("video")

    async def _track(self, kind):
        # one dict per track, as the cached property on Media hands out
        tracks = self.__dict__.setdefault("_tracks", {})
        return tracks.setdefault(
            kind,
            {
                "origname": f"{kind}.mp4",
                "pssh": None,
                "type": kind,
                "name": f"temp{kind}_{self.id}_{self.post_id}",
                "ext": "mp4",
            },
        )


def _run(tmp_path, monkeypatch, size_min=0, size_max=0, video_part=None):
    """Download one DRM item through the consumer. video_part is the start of
    the video track left by an earlier run, with its saved size. Returns
    (counters, the tracks the merge got, the requests the server saw, the
    .part files left)."""
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            auto_resume=True,
            download_limit=0,
            command="download",
            ssl_verify="false",
            cached_disabled=True,
            size_min=size_min,
            size_max=size_max,
            skip_download_script=None,
        ),
    )
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)
    monkeypatch.setattr(common_globals, "sem", asyncio.Semaphore(1), raising=False)
    for name in ("attempt", "attempt2"):
        monkeypatch.setattr(
            common_globals, name, contextvars.ContextVar(name, default=0), raising=False
        )
    for name in (
        "photo_count",
        "video_count",
        "audio_count",
        "skipped",
        "forced_skipped",
        "total_bytes_downloaded",
        "total_bytes",
    ):
        monkeypatch.setattr(common_globals, name, 0, raising=False)
    # three tries, so a retried track shows up as extra requests
    monkeypatch.setattr(
        ad,
        "download_retry",
        lambda: retries.download_retry(stop=stop_after_attempt(3), wait=wait_none()),
    )
    monkeypatch.setattr(ad, "get_download_retries", lambda: 3)
    monkeypatch.setattr(ad, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "path_to_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.common_logs, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.common_logs, "get_url_log", lambda ele: "")
    monkeypatch.setattr(dm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.auth_requests, "get_cookies_str", lambda: "")
    monkeypatch.setattr(run, "get_medialog", lambda ele: "")
    monkeypatch.setattr(run, "log_download_progress", lambda *a, **k: None)
    monkeypatch.setattr(
        run.progress_updater.download, "update_overall_task", lambda *a, **k: None
    )
    monkeypatch.setattr(run, "asyncio", SimpleNamespace(sleep=_noop))

    class _Placeholder:
        def __init__(self, ele, name):
            self.name = name

        async def init(self):
            path = tmp_path / self.name
            return SimpleNamespace(
                tempfilepath=path, trunicated_filepath=path.with_suffix(".mp4")
            )

    monkeypatch.setattr(ad.placeholder, "tempFilePlaceholder", _Placeholder)
    monkeypatch.setattr(ad.placeholder, "Placeholders", _Placeholder)

    cache = {}
    if video_part:
        (tmp_path / "tempvideo_7_5.part").write_bytes(VIDEO[:video_part])
        cache["tempvideo_7_5"] = {"content-total": len(VIDEO), "validator": None}

    async def _get_data(self, ele, item):
        return cache.get(item["name"])

    async def _set_data(self, ele, item, data):
        cache[item["name"]] = data

    merged = {}

    async def _keys(self, c, audio, video, ele):
        return None

    async def _merge(self, holder, ele, audio, video, username, model_id):
        for item in (audio, video):
            merged[item["type"]] = item["path"].read_bytes()
        return ele.mediatype, audio["total"] + video["total"]

    M = ad.AltDownloadManager
    for name, fn in (
        ("_get_data", _get_data),
        ("_set_data", _set_data),
        ("_media_item_keys_alt", _keys),
        ("_handle_result_alt", _merge),
        ("_add_download_job_task", _noop),
        ("_remove_download_job_task", _noop),
        ("_total_change_helper", _noop),
    ):
        monkeypatch.setattr(M, name, fn)
    monkeypatch.setattr(M, "_downloadspace", lambda self: None)

    seen = []

    async def handler(request):
        name = request.match_info["name"]
        rng = request.headers.get("Range")
        seen.append(f"{name} {rng}" if rng else name)
        body = TRACKS[name]
        if not rng:
            return web.Response(status=200, body=body, content_type="video/mp4")
        start = int(rng.split("=")[1].split("-")[0])
        return web.Response(
            status=206,
            body=body[start:],
            headers={"Content-Range": f"bytes {start}-{len(body) - 1}/{len(body)}"},
            content_type="video/mp4",
        )

    async def go():
        app = web.Application()
        app.router.add_get("/dash/{name}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        try:
            post = posts_.Post({"id": 5, "responseType": "post"}, 1, "model")
            ele = _DrmMedia(
                {
                    "id": 7,
                    "type": "video",
                    "canView": True,
                    "files": {"drm": {"manifest": {"dash": f"{base}/dash/m.mpd"}}},
                },
                0,
                post,
            )
            async with sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                await run.consumer(
                    [(c, ele, 1, "model")], None, [ele], asyncio.Lock()
                )
        finally:
            await runner.cleanup()

    asyncio.run(go())
    counts = {
        "videos": common_globals.video_count,
        "forced_skipped": common_globals.forced_skipped,
        "failed": common_globals.skipped,
    }
    parts = sorted(p.name for p in tmp_path.glob("*.part"))
    return counts, merged, seen, parts


SKIPPED = {"videos": 0, "forced_skipped": 1, "failed": 0}
DOWNLOADED = {"videos": 1, "forced_skipped": 0, "failed": 0}


def test_whole_video_under_min_is_skipped_once(tmp_path, monkeypatch):
    counts, merged, seen, parts = _run(tmp_path, monkeypatch, size_min=WHOLE + 1)
    assert counts == SKIPPED
    assert merged == {}
    # each track asked for once: no retries
    assert seen == ["audio.mp4", "video.mp4"]
    # the audio track downloaded before the decision isn't left behind
    assert parts == []


def test_small_audio_doesnt_skip_a_big_enough_video(tmp_path, monkeypatch):
    # the audio track alone is under the minimum, the video is not
    counts, merged, seen, parts = _run(tmp_path, monkeypatch, size_min=len(AUDIO) + 1)
    assert counts == DOWNLOADED
    assert merged == {"audio": AUDIO, "video": VIDEO}
    assert seen == ["audio.mp4", "video.mp4"]


def test_whole_video_over_max_is_skipped(tmp_path, monkeypatch):
    # each track is under the maximum, the two together are not
    counts, merged, seen, parts = _run(tmp_path, monkeypatch, size_max=WHOLE - 1)
    assert counts == SKIPPED
    assert merged == {}
    assert seen == ["audio.mp4", "video.mp4"]
    assert parts == []


def test_whole_video_within_max_is_downloaded(tmp_path, monkeypatch):
    counts, merged, seen, parts = _run(tmp_path, monkeypatch, size_max=WHOLE)
    assert counts == DOWNLOADED
    assert merged == {"audio": AUDIO, "video": VIDEO}


def test_resumed_video_under_min_is_skipped(tmp_path, monkeypatch):
    # the video's saved size decides it: no request for the video track, and
    # neither track's part is left
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, size_min=WHOLE + 1, video_part=2_000
    )
    assert counts == SKIPPED
    assert seen == ["audio.mp4"]
    assert parts == []


def test_resumed_video_big_enough_is_resumed(tmp_path, monkeypatch):
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, size_min=len(AUDIO) + 1, video_part=2_000
    )
    assert counts == DOWNLOADED
    assert seen == ["audio.mp4", "video.mp4 bytes=2000-"]
    assert merged == {"audio": AUDIO, "video": VIDEO}


def test_no_limits_downloads_both_tracks(tmp_path, monkeypatch):
    counts, merged, seen, parts = _run(tmp_path, monkeypatch)
    assert counts == DOWNLOADED
    assert merged == {"audio": AUDIO, "video": VIDEO}
    assert seen == ["audio.mp4", "video.mp4"]
