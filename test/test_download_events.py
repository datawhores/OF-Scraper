"""Download events (ofscraper/utils/events.py) for code outside core, such as
a GUI: item_downloaded when a file is saved, item_finished when the download
loop has counted an item, with why it failed or was skipped.

The normal and Fansly stream tests run run.py's consumer with the real Media
and download managers against a local server (test_size_limit_skip's
fixtures); the DRM ones run the real AltDownloadManager, merge step included,
against test_drm_size_limits' local server.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.fansly_stream_download as stream_mod
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.events as events
from ofscraper.commands.scraper.actions.download import stop
import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.sites.fansly import video as fansly_video
from test_drm_size_limits import AUDIO, VIDEO, _run
from test_size_limit_skip import (  # noqa: F401  (env and fansly are fixtures)
    BODY,
    MODEL_ID,
    STREAM_SIZE,
    USERNAME,
    counts,
    env,
    fansly,
    fansly_item,
    normal_item_run,
    photo,
    run_once,
)


@pytest.fixture
def heard(monkeypatch):
    """Every event, from a plain subscriber and an async one."""
    monkeypatch.setattr(events, "_subscribers", {})
    got = []

    def downloaded(ele, path):
        got.append(("item_downloaded", ele.id, path))

    async def finished(ele, username, result, reason):
        await asyncio.sleep(0)
        got.append(("item_finished", ele.id, username, result, reason))

    events.subscribe("item_downloaded", downloaded)
    events.subscribe("item_finished", finished)
    return got


def finished(heard):
    return [e[1:] for e in heard if e[0] == "item_finished"]


def downloads(heard):
    return [e[1:] for e in heard if e[0] == "item_downloaded"]


# ------------------------------------------------------------- normal downloader

def test_normal_download_sends_both_events_once(env, heard):
    counted, _ = normal_item_run(env)
    assert counted == counts(photo_count=1)
    (path,) = env.out.iterdir()
    assert path.read_bytes() == BODY
    assert heard == [
        ("item_downloaded", 7, path),
        ("item_finished", 7, USERNAME, "downloaded", None),
    ]


@pytest.mark.parametrize("limit", [(len(BODY) + 1, 0), (0, len(BODY) - 1)],
                         ids=["under -sm", "over -sx"])
def test_size_skip_says_size_limit(env, heard, limit):
    counted, _ = normal_item_run(env, size_min=limit[0], size_max=limit[1])
    assert counted == counts(forced_skipped=1)
    assert heard == [("item_finished", 7, USERNAME, "skipped", "size limit")]


def test_script_skip_says_skip_download_script(env, heard, monkeypatch):
    async def script(total, ele):
        return True

    monkeypatch.setattr(dm, "skip_download_script", script)
    counted, _ = normal_item_run(env)
    assert counted == counts(forced_skipped=1)
    assert heard == [("item_finished", 7, USERNAME, "skipped", "skip_download_script")]


def test_failed_download_gives_the_error_without_its_link(env, heard):
    counted, _ = normal_item_run(env, name="gone123")
    assert counted == counts(skipped=1)
    ((media_id, username, result, reason),) = finished(heard)
    assert (media_id, username, result) == (7, USERNAME, "failed")
    assert downloads(heard) == []
    assert reason and "404" in reason
    # the server's address and the file's name were only in the link
    assert "://" not in reason and "127.0.0.1" not in reason and "gone123" not in reason


def test_item_with_no_link_says_no_link(env, heard):
    post = Post({"id": 1, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
                MODEL_ID, USERNAME, responsetype="timeline")
    locked = Media({"id": 8, "type": "photo", "canView": True, "files": {}}, 0, post)

    async def go():
        await run_mod.consumer([(None, locked, MODEL_ID, USERNAME)], None, [locked],
                               asyncio.Lock())

    asyncio.run(go())
    assert heard == [("item_finished", 8, USERNAME, "failed", "no link")]


def test_failing_subscribers_dont_change_the_download(env, heard, monkeypatch, caplog):
    def broken(**kwargs):
        raise RuntimeError("plain subscriber bug")

    async def broken_async(**kwargs):
        raise RuntimeError("async subscriber bug")

    # ahead of the recording ones, which still get every event
    for name in events.EVENTS:
        monkeypatch.setitem(
            events._subscribers, name, (broken, broken_async) + events._subscribers[name]
        )
    with caplog.at_level(logging.DEBUG, logger="shared"):
        counted, _ = normal_item_run(env)
    assert counted == counts(photo_count=1)
    (path,) = env.out.iterdir()
    assert path.read_bytes() == BODY
    assert heard == [
        ("item_downloaded", 7, path),
        ("item_finished", 7, USERNAME, "downloaded", None),
    ]
    failures = [r for r in caplog.records if r.filename == "events.py"]
    assert len(failures) == 4
    assert all(r.levelno == logging.DEBUG and r.exc_info for r in failures)


@pytest.fixture
def stoppable(env, monkeypatch):
    """The env fixture stubs run.py's asyncio with only sleep; a stop needs
    its CancelledError too. The stop request is cleared afterwards."""
    monkeypatch.setattr(
        run_mod, "asyncio",
        SimpleNamespace(sleep=run_mod.asyncio.sleep, CancelledError=asyncio.CancelledError),
    )
    monkeypatch.setattr(common_globals, "stopped", 0, raising=False)
    stop.clear()
    yield env
    stop.clear()


async def _stop_and_wait(*a, **k):
    stop.request()
    # the stop cancels the download here
    await asyncio.sleep(5)
    raise AssertionError("not cancelled")


def test_stop_during_after_download_script_still_reports_the_file(stoppable, heard,
                                                                  monkeypatch):
    monkeypatch.setattr(dm, "after_download_script", _stop_and_wait)
    counted, _ = normal_item_run(stoppable)
    (path,) = stoppable.out.iterdir()
    assert path.read_bytes() == BODY
    # saved and recorded before the script: counted and reported as downloaded
    assert counted == counts(photo_count=1)
    assert common_globals.stopped == 0
    assert common_globals.total_bytes_downloaded == len(BODY)
    assert heard == [
        ("item_downloaded", 7, path),
        ("item_finished", 7, USERNAME, "downloaded", None),
    ]


def test_stop_during_the_transfer_sends_one_stopped_event(stoppable, heard, monkeypatch):
    monkeypatch.setattr(md.MainDownloadManager, "_handle_result_main", _stop_and_wait)
    counted, (ele,) = normal_item_run(stoppable)
    assert counted == counts()
    assert common_globals.stopped == 1 and ele.download_stopped
    assert heard == [("item_finished", 7, USERNAME, "stopped", None)]


def test_item_stopped_before_it_started_sends_no_event(stoppable, heard):
    ele = photo("http://127.0.0.1:9")
    stop.request()

    async def go():
        # its own task: the stop also cancels the task the item ran in
        return await asyncio.create_task(
            run_mod.handle_one((None, ele, MODEL_ID, USERNAME), None, lambda: 1)
        )

    assert asyncio.run(go()) is False
    assert ele.download_unstarted
    assert heard == []


def test_retry_inside_the_downloader_sends_each_event_once(env, heard, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_NUM_TRIES", "3")
    monkeypatch.setenv("OF_MIN_WAIT_API", "0")
    monkeypatch.setenv("OF_MAX_WAIT_API", "0")
    real = md.MainDownloadManager._main_download_sendreq
    calls = []

    async def fail_once(self, *a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("connection reset")
        return await real(self, *a, **k)

    monkeypatch.setattr(md.MainDownloadManager, "_main_download_sendreq", fail_once)
    counted, _ = normal_item_run(env)
    assert len(calls) == 2
    assert counted == counts(photo_count=1)
    (path,) = env.out.iterdir()
    assert heard == [
        ("item_downloaded", 7, path),
        ("item_finished", 7, USERNAME, "downloaded", None),
    ]


def test_no_subscribers_downloads_as_before(env, monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})
    counted, _ = normal_item_run(env)
    assert counted == counts(photo_count=1)
    assert [p.read_bytes() for p in env.out.iterdir()] == [BODY]


# ------------------------------------------------------------- Fansly stream

def test_fansly_stream_download_sends_both_events_once(env, fansly, heard):
    counted, _ = run_once(env, [fansly_item()[0]], fansly.session)
    assert counted == counts(video_count=1)
    (path,) = env.out.iterdir()
    assert path.read_bytes() == b"\0" * STREAM_SIZE
    assert heard == [
        ("item_downloaded", fansly.id, path),
        ("item_finished", fansly.id, USERNAME, "downloaded", None),
    ]


def test_fansly_stream_size_skip_says_size_limit(env, fansly, heard):
    counted, _ = run_once(env, [fansly_item()[0]], fansly.session, STREAM_SIZE + 1, 0)
    assert counted == counts(forced_skipped=1)
    assert heard == [("item_finished", fansly.id, USERNAME, "skipped", "size limit")]


def test_protected_fansly_stream_says_so(env, fansly, heard, monkeypatch):
    async def protected(self, c, best):
        raise fansly_video.ProtectedStream("protected")

    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_stream_urls", protected)
    monkeypatch.setattr(stream_mod.fansly_video, "has_direct", lambda raw: False)
    counted, _ = run_once(env, [fansly_item()[0]], fansly.session)
    assert counted == counts(forced_skipped=1)
    assert heard == [("item_finished", fansly.id, USERNAME, "skipped", "protected stream")]


# ------------------------------------------------------------- DRM

def _drm_run(tmp_path, monkeypatch, **kwargs):
    """A DRM video through the real merge step, with ffmpeg, the integrity
    check, the move and the database stubbed out."""
    final = tmp_path / "saved.mp4"

    async def merge(cmd, **kw):
        # ffmpeg's output is the command's last path
        pathlib_out = next(a for a in reversed(cmd) if a.endswith(".mp4"))
        with open(pathlib_out, "wb") as f:
            f.write(AUDIO + VIDEO)
        return SimpleNamespace(stderr=b"", stdout=b"")

    def move(temp, path, ele, **kwargs):
        temp.replace(final)
        return final

    async def no_hash(*a, **k):
        return "hash"

    async def mark(*a, **k):
        return None

    monkeypatch.setattr(ad, "async_run", merge)
    monkeypatch.setattr(ad, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(ad, "verify_media_integrity", lambda *a: True)
    monkeypatch.setattr(ad.common_paths, "moveHelper", move)
    monkeypatch.setattr(ad.common_paths, "addGlobalDir", lambda *a: None)
    monkeypatch.setattr(ad.common, "get_hash", no_hash)
    monkeypatch.setattr(ad, "mark_media_as_downloaded", mark)
    monkeypatch.setattr(dm, "after_download_script", mark)
    counted, *_ = _run(tmp_path, monkeypatch, real_merge=True, **kwargs)
    return counted, final


def test_drm_download_sends_both_events_once(tmp_path, monkeypatch, heard):
    counted, final = _drm_run(tmp_path, monkeypatch)
    assert counted == {"videos": 1, "forced_skipped": 0, "failed": 0}
    assert final.read_bytes() == AUDIO + VIDEO
    assert heard == [
        ("item_downloaded", 7, final),
        ("item_finished", 7, "model", "downloaded", None),
    ]


def test_drm_without_cdm_keys_says_so(tmp_path, monkeypatch, heard):
    monkeypatch.setattr(ad.keyhelpers, "missing_cdm_keys", lambda: "client_id.bin")
    counted, _ = _drm_run(tmp_path, monkeypatch)
    assert counted == {"videos": 0, "forced_skipped": 1, "failed": 0}
    assert heard == [("item_finished", 7, "model", "skipped", "CDM keys not found")]


def test_drm_size_skip_says_size_limit(tmp_path, monkeypatch, heard):
    counted, _ = _drm_run(tmp_path, monkeypatch, size_min=len(AUDIO + VIDEO) + 1)
    assert counted == {"videos": 0, "forced_skipped": 1, "failed": 0}
    assert heard == [("item_finished", 7, "model", "skipped", "size limit")]


# ------------------------------------------------------------- the module

def test_subscribe_checks_the_name_and_ignores_repeats(monkeypatch):
    monkeypatch.setattr(events, "_subscribers", {})
    with pytest.raises(ValueError):
        events.subscribe("item_saved", print)

    class Listener:
        def __init__(self):
            self.got = []

        def on(self, **kwargs):
            self.got.append(kwargs)

    listener = Listener()
    events.subscribe("item_finished", listener.on)
    events.subscribe("item_finished", listener.on)
    asyncio.run(events.emit("item_finished", result="downloaded"))
    assert listener.got == [{"result": "downloaded"}]
    # a bound method is a new object each time it's read
    events.unsubscribe("item_finished", listener.on)
    events.unsubscribe("item_finished", listener.on)
    asyncio.run(events.emit("item_finished", result="downloaded"))
    assert listener.got == [{"result": "downloaded"}]


def test_failure_reason_has_no_link_or_home_folder_name(monkeypatch):
    # earlier tests may leave session values (a user id, say) registered
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: "someone")
    reason = run_mod._failure_reason(Exception(
        "Media:1 got 403 from https://cdn.example/a/b.mp4?Policy=p&Signature=s\n"
        "/data/someone/b.part was not created"
    ))
    assert reason == (
        "Media:1 got 403 from {url} /data/{home_directory}/b.part was not created"
    )
    assert run_mod._failure_reason(KeyError()) == "KeyError"


# signed-link parts that must never reach a subscriber
SECRETS = ("PPP", "SSS", "KKK", "Policy", "Signature", "Key-Pair-Id")


@pytest.mark.parametrize("text, expected", [
    # aiohttp's and httpx's messages: the closing quote stays
    ("404, message='Not Found', url='https://cdn.example/a.mp4?Policy=PPP&Signature=SSS"
     "&Key-Pair-Id=KKK'", "404, message='Not Found', url='{url}'"),
    ("Client error '403' for url 'https://cdn.example/a.mp4?Signature=SSS'",
     "Client error '403' for url '{url}'"),
    # JSON-escaped
    ('{"url":"https:\\/\\/cdn.example\\/a.mp4?Policy=PPP&Signature=SSS&Key-Pair-Id=KKK"}',
     '{"url":"{url}"}'),
    # no scheme: the address stays, the query goes
    ("cdn.example/a.mp4?Policy=PPP&Signature=SSS&Key-Pair-Id=KKK failed",
     "cdn.example/a.mp4 failed"),
    ("//cdn.example/a.mp4?Expires=1&Signature=SSS&Key-Pair-Id=KKK", "{url}"),
    # percent-encoded, once and twice
    ("bad link https%3A%2F%2Fcdn.example%2Fa.mp4%3FPolicy%3DPPP%26Signature%3DSSS",
     "bad link {url}"),
    ("bad link https%253A%252F%252Fcdn.example%252Fa.mp4%253FSignature%253DSSS",
     "bad link {url}"),
    # a question in the text is left alone
    ("is it there? no", "is it there? no"),
], ids=["aiohttp", "httpx", "json", "no scheme", "no scheme //", "percent",
        "percent twice", "question"])
def test_failure_reason_lets_no_signed_link_through(monkeypatch, text, expected):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    reason = run_mod._failure_reason(Exception(text))
    assert reason == expected
    assert not any(s in reason for s in SECRETS)


def test_failure_reason_shows_an_os_error_path_as_it_is(monkeypatch):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: "someone")
    error = OSError(28, "No space left on device", r"D:\data\someone\Downloads\x.part")
    assert run_mod._failure_reason(error) == (
        r"[Errno 28] No space left on device: D:\data\{home_directory}\Downloads\x.part"
    )
    # the fourth argument is Windows' error code
    error = PermissionError(13, "Access is denied", "/data/someone/a", None, "/data/someone/b")
    assert run_mod._failure_reason(error) == (
        "[Errno 13] Access is denied: /data/{home_directory}/a -> /data/{home_directory}/b"
    )
    # no path: as str() gives it
    assert run_mod._failure_reason(OSError("disk gone")) == "disk gone"
