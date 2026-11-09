"""DRM size limits are checked on the whole video, audio + video (#316).

A DRM video downloads as two tracks. The limits were checked on each track's
size on its own, so with a minimum size the small audio track was "under
size min" for almost every video. The skip changed the item's mediatype,
which made its manifest URL None, so the video track and every retry failed
and the item was counted as failed instead of skipped.

skip_download_script skips the same way, but without changing the
mediatype, so it went unnoticed: with both tracks skipped the item failed
with "0 bytes", with one skipped it failed on the missing track's file and
left the other's .part (#325). A skipped audio track then still had the
video track downloaded in full before the item was dropped (#343).

Each test runs one DRM item through run.py's consumer (the counters), the
real AltDownloadManager and session, against a local server that serves the
two tracks. Decrypting and merging are stubbed out: they come after the
size decision.
"""

import asyncio
import contextvars
import logging
import pathlib
from types import SimpleNamespace

import pytest
from aiohttp import web
from tenacity import stop_after_attempt, wait_none

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.run as run
import ofscraper.commands.scraper.actions.download.utils.retries as retries
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

AUDIO = bytes(i % 251 for i in range(1_000))
VIDEO = bytes(i % 241 for i in range(5_000))
WHOLE = len(AUDIO) + len(VIDEO)
FILE = bytes(i % 239 for i in range(3_000))
TRACKS = {"audio.mp4": AUDIO, "video.mp4": VIDEO, "file.mp4": FILE}


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


def _run(
    tmp_path,
    monkeypatch,
    size_min=0,
    size_max=0,
    video_part=None,
    script=None,
    drm=True,
    chunked=False,
    cache_error=None,
    cache_error_times=1,
    cache_error_always=False,
    file_part=None,
):
    """Download one item through the consumer: a DRM video, or with
    drm=False a non-DRM file. With chunked the server sends each whole file
    chunked, without its size (no Content-Length). video_part is the start of
    the video track left by an earlier run, with its saved size; file_part
    the same for a non-DRM file. script
    stands in for skip_download_script: it gets each file's size and
    returns True to skip it. cache_error is raised by the first
    cache_error_times saves of a file's or track's headers after the size
    check skips it, or with cache_error_always by those saves whatever the
    size check decided. Returns (counters, the tracks the merge got, the
    requests the server saw, the .part files left). A non-DRM file's merge
    is under "file", and "marked" is set when it's saved as downloaded
    without a file."""
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
            quality=None,
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
    if file_part:
        (tmp_path / "file_7_5.part").write_bytes(FILE[:file_part])
        cache["file"] = {
            "content-total": len(FILE),
            "content-type": "video/mp4",
            "validator": None,
        }

    async def _get_data(self, ele, item):
        return cache.get(item["name"])

    cache_errors = [cache_error] * cache_error_times if cache_error else []

    def _cache_fails(ele):
        return cache_errors and (
            cache_error_always or ele.mediatype == "Forced_skipped"
        )

    async def _set_data(self, ele, item, data):
        if _cache_fails(ele):
            raise cache_errors.pop()
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

    if script:

        async def _script(total, ele):
            return script(total)

        monkeypatch.setattr(dm, "skip_download_script", _script)

    if not drm:

        async def _get_data_main(self, ele):
            return cache.get("file")

        async def _set_data_main(self, ele, data):
            if _cache_fails(ele):
                raise cache_errors.pop()
            cache["file"] = data

        async def _handle_main(self, result, ele, username, model_id):
            merged["file"] = pathlib.Path(result[1]).read_bytes()
            return ele.mediatype, result[0]

        async def _mark(ele, filepath=None, downloaded=None, **kwargs):
            # the database row the real _force_download saves
            assert filepath is None and downloaded is True
            merged["marked"] = True

        monkeypatch.setattr(dm, "mark_media_as_downloaded", _mark)

        N = md.MainDownloadManager
        for name, fn in (
            ("_get_data", _get_data_main),
            ("_set_data", _set_data_main),
            ("_handle_result_main", _handle_main),
            ("_add_download_job_task", _noop),
            ("_remove_download_job_task", _noop),
            ("_total_change_helper", _noop),
        ):
            monkeypatch.setattr(N, name, fn)
        monkeypatch.setattr(N, "_downloadspace", lambda self: None)
        monkeypatch.setattr(
            md,
            "download_retry",
            lambda: retries.download_retry(stop=stop_after_attempt(3), wait=wait_none()),
        )
        monkeypatch.setattr(md, "get_download_retries", lambda: 3)
        monkeypatch.setattr(md, "send_chunk_msg", lambda *a, **k: None)
        monkeypatch.setattr(md.common_logs, "path_to_file_logger", lambda *a, **k: None)

    seen = []

    async def handler(request):
        name = request.match_info["name"]
        rng = request.headers.get("Range")
        seen.append(f"{name} {rng}" if rng else name)
        body = TRACKS[name]
        if not rng and chunked:
            resp = web.StreamResponse(headers={"Content-Type": "video/mp4"})
            resp.enable_chunked_encoding()
            await resp.prepare(request)
            for i in range(0, len(body), 1024):
                await resp.write(body[i : i + 1024])
            await resp.write_eof()
            return resp
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
            files = (
                {"drm": {"manifest": {"dash": f"{base}/dash/m.mpd"}}}
                if drm
                else {"full": {"url": f"{base}/dash/file.mp4"}}
            )
            ele = (_DrmMedia if drm else Media)(
                {"id": 7, "type": "video", "canView": True, "files": files},
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

# tracks sent with their size, and without it (chunked, no Content-Length):
# then the size is known only once the track is written (#336)
REPLIES = pytest.mark.parametrize("chunked", [False, True], ids=["sized", "no size"])


@REPLIES
def test_whole_video_under_min_is_skipped_once(tmp_path, monkeypatch, chunked):
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, size_min=WHOLE + 1, chunked=chunked
    )
    assert counts == SKIPPED
    assert merged == {}
    # each track asked for once: no retries
    assert seen == ["audio.mp4", "video.mp4"]
    # the audio track downloaded before the decision isn't left behind
    assert parts == []


@REPLIES
def test_small_audio_doesnt_skip_a_big_enough_video(tmp_path, monkeypatch, chunked):
    # the audio track alone is under the minimum, the video is not
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, size_min=len(AUDIO) + 1, chunked=chunked
    )
    assert counts == DOWNLOADED
    assert merged == {"audio": AUDIO, "video": VIDEO}
    assert seen == ["audio.mp4", "video.mp4"]


@REPLIES
def test_whole_video_over_max_is_skipped(tmp_path, monkeypatch, chunked):
    # each track is under the maximum, the two together are not
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, size_max=WHOLE - 1, chunked=chunked
    )
    assert counts == SKIPPED
    assert merged == {}
    assert seen == ["audio.mp4", "video.mp4"]
    assert parts == []


@REPLIES
def test_whole_video_within_max_is_downloaded(tmp_path, monkeypatch, chunked):
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, size_max=WHOLE, chunked=chunked
    )
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


@REPLIES
def test_no_limits_downloads_both_tracks(tmp_path, monkeypatch, chunked):
    counts, merged, seen, parts = _run(tmp_path, monkeypatch, chunked=chunked)
    assert counts == DOWNLOADED
    assert merged == {"audio": AUDIO, "video": VIDEO}
    assert seen == ["audio.mp4", "video.mp4"]


@pytest.mark.parametrize(
    "skipped",
    [
        pytest.param({len(AUDIO), len(VIDEO)}, id="both"),
        pytest.param({len(AUDIO)}, id="audio"),
        pytest.param({len(VIDEO)}, id="video"),
    ],
)
@REPLIES
def test_script_skip_skips_the_whole_video(tmp_path, monkeypatch, skipped, chunked):
    # a skip by skip_download_script, of either track or both, skips the
    # item: counted as skipped, not failed, and no track's part is left
    calls = []

    def script(total):
        calls.append(total)
        return total in skipped

    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, script=script, chunked=chunked
    )
    assert counts == SKIPPED
    assert merged == {}
    if len(AUDIO) in skipped:
        # a skipped audio track skips the whole video, so the video track
        # isn't asked for, nor the script about it (#343)
        assert calls == [len(AUDIO)]
        assert seen == ["audio.mp4"]
    else:
        # the script is asked about each track, once: no retries
        assert calls == [len(AUDIO), len(VIDEO)]
        assert seen == ["audio.mp4", "video.mp4"]
    assert parts == []


def test_script_skip_of_audio_removes_an_earlier_video_part(tmp_path, monkeypatch):
    # the video track isn't asked for, and its part left by an earlier run
    # is removed, as when the video track was downloaded and then dropped
    calls = []

    def script(total):
        calls.append(total)
        return total == len(AUDIO)

    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, video_part=2_000, script=script
    )
    assert counts == SKIPPED
    assert merged == {}
    assert calls == [len(AUDIO)]
    assert seen == ["audio.mp4"]
    assert parts == []


def test_script_skip_of_a_resumed_video_removes_its_part(tmp_path, monkeypatch):
    # the video's saved size is what the script is asked about; the part
    # left by the earlier run isn't kept
    counts, merged, seen, parts = _run(
        tmp_path,
        monkeypatch,
        video_part=2_000,
        script=lambda total: total == len(VIDEO),
    )
    assert counts == SKIPPED
    assert merged == {}
    assert seen == ["audio.mp4"]
    assert parts == []


@REPLIES
def test_script_that_skips_nothing_downloads_both_tracks(tmp_path, monkeypatch, chunked):
    calls = []

    def script(total):
        calls.append(total)
        return False

    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, script=script, chunked=chunked
    )
    assert counts == DOWNLOADED
    assert merged == {"audio": AUDIO, "video": VIDEO}
    assert calls == [len(AUDIO), len(VIDEO)]
    assert seen == ["audio.mp4", "video.mp4"]


@REPLIES
@pytest.mark.parametrize("skip", [True, False])
def test_script_on_a_non_drm_file_is_unchanged(tmp_path, monkeypatch, skip, chunked):
    calls = []

    def script(total):
        calls.append(total)
        return skip

    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, script=script, drm=False, chunked=chunked
    )
    assert seen == ["file.mp4"]
    # asked once, with the file's real size
    assert calls == [len(FILE)]
    if skip:
        # a skipped file leaves no part (the merge is stubbed out, so a
        # downloaded one's part stays here)
        assert parts == []
    # a skipped non-DRM file is saved as downloaded without a file and
    # counted as a video, as before
    assert counts == DOWNLOADED
    assert merged == ({"marked": True} if skip else {"file": FILE})


# ------------------------------------------------------------- after-action script

def _script_media(tmp_path, monkeypatch, items):
    """The media the real after_download_action_script would send on stdin."""
    import json

    import ofscraper.managers.manager as manager
    import ofscraper.scripts.after_download_action_script as script_mod

    script = tmp_path / "script"
    script.write_text("")
    monkeypatch.setattr(
        settings, "get_settings",
        lambda *a, **k: SimpleNamespace(after_action_script=str(script)),
    )
    monkeypatch.setattr(manager, "Manager", SimpleNamespace(current_model_manager=SimpleNamespace(
        get_model=lambda username: {"username": username, "id": 1})))
    sent = []
    monkeypatch.setattr(script_mod, "run", lambda cmd, input=None, **k: sent.append(input))
    script_mod.after_download_action_script("model", items)
    (payload,) = sent
    return json.loads(payload)["media"]


def _run_with_payload(tmp_path, monkeypatch, **kwargs):
    """_run, plus the media the after-action script gets for the item."""
    items = []
    consumer = run.consumer

    async def recording_consumer(aws, *args, **kw):
        items.extend(ele for _, ele, *_ in aws)
        return await consumer(aws, *args, **kw)

    monkeypatch.setattr(run, "consumer", recording_consumer)
    result = _run(tmp_path, monkeypatch, **kwargs)
    (media,) = _script_media(tmp_path, monkeypatch, items)
    return (*result, media)


LOCKED = RuntimeError("database is locked")
LIMITS = pytest.mark.parametrize(
    "limit",
    [{"size_min": WHOLE + 1}, {"size_max": WHOLE - 1}],
    ids=["under min", "over max"],
)


@LIMITS
def test_size_skipped_video_stays_skipped_after_a_later_error(
    tmp_path, monkeypatch, limit
):
    # the size check skips the video, then saving the video track's headers
    # fails. The skip stands: no retry (the skip leaves the item no manifest
    # to fetch the track from), no part left, nothing saved (#345)
    counts, merged, seen, parts, media = _run_with_payload(
        tmp_path, monkeypatch, cache_error=LOCKED, **limit
    )
    assert counts == SKIPPED
    # not merged, so not saved as downloaded
    assert merged == {}
    assert seen == ["audio.mp4", "video.mp4"]
    assert parts == []
    assert media["download_status"] == "skipped"
    assert media["type"] == "video"


@LIMITS
@pytest.mark.parametrize("times", [1, 3], ids=["once", "every try"])
def test_size_skipped_file_stays_skipped_after_a_later_error(
    tmp_path, monkeypatch, limit, times
):
    # the same for a non-DRM file: an error after the size check skipped it
    # ends the attempt as skipped, without asking for the file again
    limit = {k: len(FILE) + (1 if k == "size_min" else -1) for k in limit}
    counts, merged, seen, parts, media = _run_with_payload(
        tmp_path,
        monkeypatch,
        drm=False,
        cache_error=LOCKED,
        cache_error_times=times,
        **limit,
    )
    assert counts == SKIPPED
    # neither moved into place nor saved as downloaded without a file
    assert merged == {}
    assert seen == ["file.mp4"]
    assert parts == []
    assert media["download_status"] == "skipped"
    assert media["type"] == "video"


@pytest.mark.parametrize("drm", [True, False], ids=["drm", "non-drm"])
def test_error_without_a_size_skip_still_retries_and_fails(
    tmp_path, monkeypatch, drm
):
    # no limit is hit: an error on every try fails the item, as before, and
    # the part is kept for the next run to resume
    counts, merged, seen, parts, media = _run_with_payload(
        tmp_path,
        monkeypatch,
        drm=drm,
        cache_error=LOCKED,
        cache_error_times=3,
        cache_error_always=True,
        size_min=1,
    )
    assert counts == {"videos": 0, "forced_skipped": 0, "failed": 1}
    assert merged == {}
    if drm:
        # the retry resumes the audio part from the size the first try got.
        # The test server sends the whole track in one chunk, so it's all on
        # disk and the test server answers the resume with an empty 206,
        # which fails without more tries, as before
        assert seen == ["audio.mp4", "audio.mp4 bytes=1000-"]
    else:
        assert seen == ["file.mp4"] * 3
    assert len(parts) == 1
    assert media["download_status"] == "failed"
    assert media["type"] == "video"


def test_size_skipped_video_that_fails_reaches_the_script_with_its_type(
    tmp_path, monkeypatch
):
    # the size check labels the video Forced_skipped, then removing the
    # tracks' parts fails. That's outside the retries, so the item ends
    # failed: the script still gets its own type, not the label (#341)
    class _Path(type(pathlib.Path())):
        def unlink(self, missing_ok=False):
            raise PermissionError("the file is in use")

    monkeypatch.setattr(ad, "pathlib", SimpleNamespace(Path=_Path))
    counts, merged, seen, parts, media = _run_with_payload(
        tmp_path, monkeypatch, size_min=WHOLE + 1
    )
    assert counts == {"videos": 0, "forced_skipped": 0, "failed": 1}
    assert merged == {}
    assert seen == ["audio.mp4", "video.mp4"]
    assert media["download_status"] == "failed"
    assert media["type"] == "video"


def test_size_skipped_video_reaches_the_script_as_skipped(tmp_path, monkeypatch):
    counts, *_, media = _run_with_payload(tmp_path, monkeypatch, size_min=WHOLE + 1)
    assert counts == SKIPPED
    assert media["download_status"] == "skipped"
    assert media["type"] == "video"


# ------------------------------------------------- resumed non-DRM file (#348)

FILE_LIMITS = pytest.mark.parametrize(
    "limit",
    [{"size_min": len(FILE) + 1}, {"size_max": len(FILE) - 1}],
    ids=["under min", "over max"],
)


@FILE_LIMITS
def test_resumed_file_skipped_by_a_size_limit_removes_its_part(
    tmp_path, monkeypatch, limit
):
    # the saved size decides it: no request, counted as skipped, and the
    # part left by the earlier run is removed, as a DRM video's are
    counts, merged, seen, parts, media = _run_with_payload(
        tmp_path, monkeypatch, drm=False, file_part=1_000, **limit
    )
    assert counts == SKIPPED
    assert merged == {}
    assert seen == []
    assert parts == []
    assert media["download_status"] == "skipped"


def test_script_skip_of_a_resumed_file_removes_its_part(tmp_path, monkeypatch):
    # skip_download_script is asked about the saved size, without a request.
    # The part goes too; the file is still saved as done without a file and
    # counted as a video, as for a script skip of a file that wasn't resumed
    calls = []

    def script(total):
        calls.append(total)
        return True

    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, drm=False, file_part=1_000, script=script
    )
    assert calls == [len(FILE)]
    assert seen == []
    assert parts == []
    assert counts == DOWNLOADED
    assert merged == {"marked": True}


@pytest.mark.parametrize(
    "limit",
    [{}, {"size_min": len(FILE)}, {"size_max": len(FILE)}],
    ids=["no limit", "at min", "at max"],
)
def test_resumed_file_inside_the_limits_is_resumed(tmp_path, monkeypatch, limit):
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, drm=False, file_part=1_000, **limit
    )
    assert counts == DOWNLOADED
    assert seen == ["file.mp4 bytes=1000-"]
    assert merged == {"file": FILE}
    # the merge is stubbed out, so the finished part stays here
    assert parts == ["file_7_5.part"]


@LIMITS
def test_resumed_video_skipped_by_a_size_limit_is_unchanged(
    tmp_path, monkeypatch, limit
):
    # a DRM video with a video track part from an earlier run, as before
    counts, merged, seen, parts = _run(
        tmp_path, monkeypatch, video_part=2_000, **limit
    )
    assert counts == SKIPPED
    assert merged == {}
    assert seen == ["audio.mp4"]
    assert parts == []


