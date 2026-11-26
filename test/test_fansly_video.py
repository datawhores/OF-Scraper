"""Fansly video: best delivery, HLS and DASH through ffmpeg, re-runs.

The account-media fixture is a sanitised capture. No master playlist or MPD
was captured, so the ones used here are written by the tests.
"""

import asyncio
import errno
import contextlib
import copy
import json
import logging
import math
import pathlib
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlparse

import aiohttp
import pytest

from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.commands.db as db_command
import ofscraper.commands.metadata.manager as meta_mod
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.fansly_stream_download as stream_mod
import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.filters.media.filters as filters
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.managers.sessionmanager import ofsession
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import normalize, video

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "fansly"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/140.0"
TEST_SIGNED = {"Key-Pair-Id": "KP-TEST-1", "Signature": "SIG-TEST-2", "Policy": "POL-TEST-3"}
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe not on PATH")

MASTER = (
    "#EXTM3U\n#EXT-X-VERSION:4\n#EXT-X-INDEPENDENT-SEGMENTS\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=400000,AVERAGE-BANDWIDTH=380000,RESOLUTION=640x360,CODECS="avc1.64001e,mp4a.40.2"\n'
    "r360/media.m3u8\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=9000000,AVERAGE-BANDWIDTH=8000000,RESOLUTION=3840x2160,CODECS="avc1.640033,mp4a.40.2"\n'
    "r2160/media.m3u8\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2"\n'
    "r1080/media.m3u8\n"
)
EMPTY_MASTER = "#EXTM3U\n#EXT-X-VERSION:4\n#EXT-X-INDEPENDENT-SEGMENTS\n"
PROTECTED_MPD = (
    '<?xml version="1.0"?>\n<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static">'
    "<Period><AdaptationSet mimeType=\"video/mp4\">"
    '<ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc"/>'
    '<Representation id="1" width="3840" height="2160" bandwidth="9000000"/>'
    "</AdaptationSet></Period></MPD>\n"
)


# ------------------------------------------------------------------ helpers

def raw_media():
    data = json.loads((FIXTURES / "video_4k_account_media.json").read_text(encoding="utf-8"))
    return copy.deepcopy(data["response"][0])


def variant(media, mime):
    return next(v for v in media["variants"] if v["mimetype"] == mime)


def drop_variant(raw, mime):
    raw["media"]["variants"] = [v for v in raw["media"]["variants"] if v["mimetype"] != mime]
    return raw


def make_ele(account_media, direct=True):
    raw = account_media["media"]
    direct_url = next(
        (loc["location"] for loc in raw.get("locations") or [] if str(loc["locationId"]) == "1"),
        None,
    ) if direct else None
    media = {
        "id": int(raw["id"]),
        "type": "video",
        "canView": True,
        "files": {"full": {"url": direct_url}},
        "fansly": {
            "accountMediaId": account_media["id"],
            "mediaId": raw["id"],
            "isPreview": False,
            "media": raw,
        },
    }
    post = Post(
        {"id": 100000000000000005, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        100000000000000002,
        "a-creator",
        responsetype="timeline",
    )
    return Media(media, 0, post)


def point_at(raw, mime, base):
    """Move a stream variant's location (and the direct file's) to the local test server."""
    for direct in raw.get("locations") or []:
        direct["location"] = base + urlparse(direct["location"]).path
    loc = variant(raw, mime)["locations"][0]
    loc["location"] = base + urlparse(loc["location"]).path
    loc["metadata"] = dict(TEST_SIGNED)
    set_duration(raw, 3.0)  # what the tests generate with ffmpeg is 3 s long
    return loc["location"]


def set_duration(raw, seconds):
    """Set the metadata ``duration`` of the media and its variants (None removes it)."""
    for obj in [raw] + list(raw.get("variants") or []):
        meta = json.loads(obj.get("metadata") or "{}")
        if "duration" in meta or obj is raw:
            meta.pop("duration", None)
            if seconds is not None:
                meta["duration"] = seconds
            obj["metadata"] = json.dumps(meta)


class FakeResponse:
    def __init__(self, body, status=200):
        self.ok = status < 400
        self.status = status
        self._body = body

    async def text_(self):
        return self._body


class FakeSession:
    def __init__(self, bodies):
        self.bodies = bodies
        self.calls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.bodies.get(url), Exception):
            raise self.bodies[url]  # as the session does for a status other than 404
        yield FakeResponse(self.bodies.get(url, ""), 200 if url in self.bodies else 404)


@pytest.fixture
def env(monkeypatch, tmp_path):
    real = settings.get_settings()
    stub = SimpleNamespace(**{
        **dict(real), "site": "fansly", "verify_all_integrity": True, "size_max": 0,
        "size_min": 0, "auto_resume": True, "force_all": False, "force_model_unique": False, "download_sems": 2,
        "ssl_verify": "default", "download_limit": 0, "proxy": None, "hash": "xxh128",
    })
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    # the download globals, without the shared logger (it writes to the user's log folder)
    common_globals.set_up_contexvars()
    pool = ThreadPoolExecutor(max_workers=4)
    for name, value in {
        "thread": pool, "sem": asyncio.Semaphore(2), "lock": asyncio.Lock(),
        "log": logging.getLogger("shared"), "dirSet": set(), "localDirSet": set(),
        "fileHashes": {}, "total_bytes": 0,
    }.items():
        monkeypatch.setattr(common_globals, name, value, raising=False)
    monkeypatch.setattr(fansly_auth, "read_auth", lambda *a, **k: {"user_agent": UA})
    # A refused file is tried again at once. The real waits (2 to 3 seconds
    # before each new try of a request and of a download) are not what these
    # tests are about, and made every test with a refused file take over
    # half a minute.
    real_getattr = of_env.getattr
    monkeypatch.setattr(
        of_env, "getattr",
        lambda key, *a, **k: 0 if key in ("OF_MIN_WAIT_API", "OF_MAX_WAIT_API")
        else real_getattr(key, *a, **k))

    out_dir, temp_dir = tmp_path / "out", tmp_path / "temp"
    out_dir.mkdir()
    temp_dir.mkdir()

    class FakePlaceholders:
        def __init__(self, ele, ext):
            self.filename = f"{ele.filename}.{ext}"
            self.filepath = self.trunicated_filepath = out_dir / self.filename

        async def init(self):
            return self

    class FakeTemp:
        def __init__(self, ele, name):
            self.tempfilepath = temp_dir / name

        async def init(self):
            return self

    monkeypatch.setattr(stream_mod, "placeholder",
                        SimpleNamespace(Placeholders=FakePlaceholders, tempFilePlaceholder=FakeTemp))
    marks = []

    async def mark(ele, **kw):
        marks.append((ele.id, kw))

    async def noop(*a, **k):
        return None

    async def no_skip(*a, **k):
        return False

    # never let a test fall through to the normal downloader and its real URL
    async def no_main_download(self, *a, **k):
        raise AssertionError("normal downloader used")

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", no_main_download)
    monkeypatch.setattr(stream_mod, "mark_media_as_downloaded", mark)
    monkeypatch.setattr(stream_mod, "set_profile_cache", noop)
    monkeypatch.setattr(dm, "after_download_script", noop)
    monkeypatch.setattr(dm, "skip_download_script", no_skip)
    monkeypatch.setattr(dm.system, "check_free_size", lambda: True)
    ffmpeg_runs, ffmpeg_procs, ffmpeg_cwds, ffmpeg_timeouts = [], [], [], []
    if FFMPEG:
        monkeypatch.setattr(stream_mod, "get_ffmpeg", lambda: FFMPEG)
    else:
        monkeypatch.setattr(stream_mod, "get_ffmpeg", lambda: "ffmpeg")
    real_run_process = getattr(stream_mod, "_run_process", None)

    def counting_run(proc, cmd, timeout, cwd=None):
        ffmpeg_runs.append(cmd)
        ffmpeg_procs.append(proc)
        ffmpeg_cwds.append(cwd)
        ffmpeg_timeouts.append(timeout)
        return real_run_process(proc, cmd, timeout, cwd)

    # raising=False: the tests can also be run against code without these
    monkeypatch.setattr(stream_mod, "_run_process", counting_run, raising=False)
    # the test hook for the local http server; real runs allow https only
    monkeypatch.setattr(video, "ALLOWED_SCHEMES", ("https", "http"), raising=False)
    yield SimpleNamespace(out=out_dir, temp=temp_dir, marks=marks, stub=stub,
                          ffmpeg_runs=ffmpeg_runs, ffmpeg_procs=ffmpeg_procs,
                          ffmpeg_cwds=ffmpeg_cwds, ffmpeg_timeouts=ffmpeg_timeouts)
    pool.shutdown(wait=True)


def files_in(*dirs):
    return sorted(p.name for d in dirs for p in d.rglob("*") if p.is_file())


class Server:
    """Serves files from a dict and records every request's path and headers.

    A path in ``slow`` misbehaves: "stall" sends the headers and 188 bytes,
    then nothing; "half" sends the file's real length and half its bytes, then
    nothing; "trickle" sends one byte every 0.2 s. Each stops when the
    server shuts down, or after ``slow_limit`` seconds, so an unfixed
    downloader fails a test instead of hanging it.
    """

    def __init__(self, files, slow=None, slow_limit=30):
        self.files = files
        self.slow = slow or {}
        self.seen = []
        self.release = threading.Event()
        # paths answered with a 404 this many more times; seconds to wait
        # before sending a path; how many requests were open at once, at most
        self.fail = {}
        self.refuse = set()  # paths always answered with a 403
        self.delay = {}
        self.active = self.peak = 0
        self.count_lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with outer.count_lock:
                    outer.active += 1
                    outer.peak = max(outer.peak, outer.active)
                try:
                    self.answer()
                finally:
                    with outer.count_lock:
                        outer.active -= 1

            def answer(self):
                path = urlparse(self.path).path
                outer.seen.append((path, {k.lower(): v for k, v in self.headers.items()}))
                if outer.fail.get(path):
                    outer.fail[path] -= 1
                    self.send_error(404)
                    return
                if path in outer.refuse:
                    self.send_error(403)
                    return
                if outer.delay.get(path):
                    time.sleep(outer.delay[path])
                mode = outer.slow.get(path)
                if mode:
                    real = outer.files.get(path) or b""
                    self.send_response(200)
                    if mode == "half":  # the real length, then half of the real bytes
                        self.send_header("Content-Length", str(len(real)))
                        self.end_headers()
                        self.wfile.write(real[: len(real) // 2 // 188 * 188])
                    else:
                        self.send_header("Content-Length", "5000000")
                        self.end_headers()
                        self.wfile.write(b"\x47" + b"\xff" * 187)
                    self.wfile.flush()
                    deadline = time.monotonic() + slow_limit
                    while mode == "trickle" and time.monotonic() < deadline:
                        if outer.release.wait(0.2):
                            return
                        try:
                            self.wfile.write(b"\xff")
                            self.wfile.flush()
                        except OSError:
                            return
                    outer.release.wait(max(0, deadline - time.monotonic()))
                    return
                body = outer.files.get(path)
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self):
        return f"http://localhost:{self.httpd.server_address[1]}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


SOURCE = ["-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=3",
          "-f", "lavfi", "-i", "sine=frequency=440:duration=3"]


def ffmpeg_make(args, cwd, source=None):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *(source or SOURCE),
           "-c:v", "mpeg4", "-g", "10", "-c:a", "aac", "-shortest", *args]
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


def probe(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type:format=duration,format_name",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def assert_cdn_request(headers):
    cookie = headers.get("cookie", "")
    for k, v in TEST_SIGNED.items():
        assert f"CloudFront-{k}={v}" in cookie
    assert headers.get("origin") == "https://fansly.com"
    assert headers.get("referer") == "https://fansly.com/"
    assert headers.get("user-agent") == UA
    assert "authorization" not in headers


async def run_download(c, ele):
    return await run_mod.download(c, ele, 100000000000000002, "a-creator")


# ------------------------------------------------------------------ DoD 1

def test_4k_stream_is_chosen_over_the_720p_direct_file():
    raw = raw_media()["media"]
    assert (raw["width"], raw["height"]) == (1280, 720)
    best = video.select_best(raw)
    assert best.kind == video.HLS
    assert (best.width, best.height) == (3840, 2160)
    assert best.url == variant(raw, video.HLS_MIME)["locations"][0]["location"]
    kinds = {c.kind: (c.width, c.height) for c in video.candidates(raw)}
    assert kinds == {video.DIRECT: (1280, 720), video.HLS: (3840, 2160), video.DASH: (3840, 2160)}


def test_ties_prefer_direct_then_hls_then_dash():
    raw = raw_media()["media"]
    for v in raw["variants"]:
        if v["mimetype"] in (video.HLS_MIME, video.DASH_MIME):
            v["width"], v["height"], v["metadata"] = 1280, 720, "{}"
    assert video.select_best(raw).kind == video.DIRECT
    del raw["locations"]
    assert video.select_best(raw).kind == video.HLS


def test_cloudfront_cookies_come_from_metadata_or_the_url_query():
    assert video.cloudfront_cookies({"location": "https://x/a.m3u8", "metadata": dict(TEST_SIGNED)}) == {
        "CloudFront-Policy": "POL-TEST-3", "CloudFront-Key-Pair-Id": "KP-TEST-1",
        "CloudFront-Signature": "SIG-TEST-2"}
    url = "https://x/a.m3u8?Policy=P1&Key-Pair-Id=K1&Signature=S1"
    assert video.cloudfront_cookies({"location": url}) == {
        "CloudFront-Policy": "P1", "CloudFront-Key-Pair-Id": "K1", "CloudFront-Signature": "S1"}


def test_only_fansly_items_on_a_fansly_run_take_the_stream_path(env):
    ele = make_ele(raw_media())
    assert video.uses_stream(ele) is True
    env.stub.site = "onlyfans"
    assert video.uses_stream(ele) is False
    env.stub.site = "fansly"
    assert video.uses_stream(make_ele(drop_variant(drop_variant(raw_media(), video.HLS_MIME),
                                                   video.DASH_MIME))) is False


def test_onlyfans_items_keep_the_normal_downloader(env, monkeypatch):
    env.stub.site = "onlyfans"
    calls = []

    async def main_download(self, c, ele, username, model_id):
        calls.append(ele.id)
        return "videos", 1

    async def stream_download(self, *a):
        raise AssertionError("stream path used for an OnlyFans item")

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    monkeypatch.setattr(run_mod.FanslyStreamDownloadManager, "stream_download", stream_download)
    post = Post({"id": 1, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""}, 2, "a-creator")
    of_ele = Media({"id": 7, "type": "video", "canView": True,
                    "files": {"full": {"url": "https://cdn.example/files/abc.mp4"}}}, 0, post)
    assert asyncio.run(run_download(None, of_ele)) == ("videos", 1)
    assert calls == [7]


def test_fansly_item_whose_best_is_a_stream_takes_the_stream_path(env, monkeypatch):
    calls = []

    async def main_download(self, *a):
        raise AssertionError("normal downloader used for a 4K stream")

    async def stream_download(self, c, ele, username, model_id):
        calls.append(ele.id)
        return "videos", 1

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    monkeypatch.setattr(run_mod.FanslyStreamDownloadManager, "stream_download", stream_download)
    ele = make_ele(raw_media())
    assert asyncio.run(run_download(None, ele)) == ("videos", 1)
    assert calls == [ele.id]


# ------------------------------------------------------------------ DoD 2

def test_master_playlist_picks_the_largest_rendition():
    base = "https://cdn3.fansly.com/new/1/2/2.m3u8"
    assert video.best_rendition_url(MASTER, base) == "https://cdn3.fansly.com/new/1/2/r2160/media.m3u8"


def test_a_media_playlist_is_used_as_it_is():
    text = (FIXTURES / "media_playlist.m3u8").read_text(encoding="utf-8")
    assert video.best_rendition_url(text, "https://x/a.m3u8") == "https://x/a.m3u8"


def test_empty_master_fails_clearly_and_saves_nothing(env, caplog):
    raw = raw_media()
    hls_url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
    ele = make_ele(raw, direct=False)
    session = FakeSession({hls_url: EMPTY_MASTER})
    with pytest.raises(video.EmptyMasterPlaylist):
        video.best_rendition_url(EMPTY_MASTER, hls_url)
    result = asyncio.run(run_download(session, ele))
    assert result == ("skipped", 0)
    assert files_in(env.out, env.temp) == []
    assert env.ffmpeg_runs == [] and env.marks == []
    # the master is fetched once, with the CloudFront cookies, never guessing other names
    assert [u for u, _ in session.calls] == [hls_url]
    kw = session.calls[0][1]
    assert set(kw["cookies"]) == {"CloudFront-Policy", "CloudFront-Key-Pair-Id", "CloudFront-Signature"}
    assert kw["actions"] == [stream_mod.HEADERS]


# ------------------------------------------------------------------ DoD 3

@needs_ffmpeg
def test_hls_stream_is_copied_into_one_playable_mp4(env, tmp_path):
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()
    # dump_extra repeats the video headers on every keyframe, as real HLS
    # segments do, so each segment can be decoded on its own
    ffmpeg_make(["-bsf:v", "dump_extra=freq=keyframe", "-f", "segment", "-segment_time", "1",
                 "-segment_format", "mpegts", "segment-%d.ts"], seg_dir)
    segments = sorted(p.name for p in seg_dir.glob("segment-*.ts"))
    assert segments == ["segment-0.ts", "segment-1.ts", "segment-2.ts"]

    raw = raw_media()
    with Server({}) as srv:
        url = point_at(raw["media"], video.HLS_MIME, srv.base)
        root = urlparse(url).path.rsplit("/", 1)[0]
        srv.files.update({
            urlparse(url).path: MASTER.encode(),
            f"{root}/r2160/media.m3u8": (FIXTURES / "media_playlist.m3u8").read_bytes(),
            **{f"{root}/r2160/{name}": (seg_dir / name).read_bytes() for name in segments},
        })
        ele = make_ele(raw)

        async def go():
            async with ofsession.download_session() as c:
                return await run_download(c, ele)

        result = asyncio.run(go())

    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert files_in(env.out, env.temp) == [out.name]
    info = probe(out)
    assert "mp4" in info["format"]["format_name"]
    assert sorted(s["codec_type"] for s in info["streams"]) == ["audio", "video"]
    assert 2.0 < float(info["format"]["duration"]) < 4.0

    requested = [p for p, _ in srv.seen]
    assert requested[0] == urlparse(url).path
    assert f"{root}/r2160/media.m3u8" in requested
    assert all(f"{root}/r2160/{n}" in requested for n in segments)
    assert not any("/r360/" in p or "/r1080/" in p for p in requested)
    assert not any(p.endswith(".mp4") for p in requested)  # the 720p direct file
    for _, headers in srv.seen:
        assert_cdn_request(headers)
    assert len(env.marks) == 1
    mark_id, kw = env.marks[0]
    assert mark_id == ele.id and kw["downloaded"] is True and kw["hashdata"]
    assert pathlib.Path(kw["filepath"]) == out and kw["size"] == out.stat().st_size


# ------------------------------------------------------------------ DoD 4

def test_dash_is_used_when_there_is_no_hls():
    raw = drop_variant(raw_media(), video.HLS_MIME)["media"]
    best = video.select_best(raw)
    assert best.kind == video.DASH and (best.width, best.height) == (3840, 2160)


def test_protected_dash_is_reported_and_writes_no_file(env, caplog):
    raw = drop_variant(raw_media(), video.HLS_MIME)
    dash_url = variant(raw["media"], video.DASH_MIME)["locations"][0]["location"]
    ele = make_ele(raw, direct=False)
    session = FakeSession({dash_url: PROTECTED_MPD})
    with caplog.at_level("INFO"):
        result = asyncio.run(run_download(session, ele))
    assert result == ("forced_skipped", 0)
    assert files_in(env.out, env.temp) == []
    assert env.ffmpeg_runs == [] and env.marks == []
    assert video.dash_is_protected(PROTECTED_MPD)
    assert not video.dash_is_protected(PROTECTED_MPD.replace("ContentProtection", "SupplementalProperty"))


@needs_ffmpeg
def test_unprotected_dash_merges_video_and_audio(env, tmp_path):
    raw = drop_variant(raw_media(), video.HLS_MIME)
    with Server({}) as srv:
        url = point_at(raw["media"], video.DASH_MIME, srv.base)
        name = urlparse(url).path.rsplit("/", 1)[1]
        dash_dir = tmp_path / "dash"
        dash_dir.mkdir()
        ffmpeg_make(["-f", "dash", "-seg_duration", "1", name], dash_dir)
        root = urlparse(url).path.rsplit("/", 1)[0]
        srv.files.update({f"{root}/{p.name}": p.read_bytes() for p in dash_dir.iterdir()})
        ele = make_ele(raw)

        async def go():
            async with ofsession.download_session() as c:
                return await run_download(c, ele)

        result = asyncio.run(go())

    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert files_in(env.out, env.temp) == [out.name]
    assert sorted(s["codec_type"] for s in probe(out)["streams"]) == ["audio", "video"]
    assert len(srv.seen) > 2
    for _, headers in srv.seen:
        assert_cdn_request(headers)


# ------------------------------------------------------------------ DoD 5

def test_rerun_downloads_nothing(env, monkeypatch):
    raw = raw_media()
    hls_url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
    session = FakeSession({hls_url: (FIXTURES / "media_playlist.m3u8").read_text(encoding="utf-8")})
    stream_runs = []

    async def fake_copy(self, c, best, url, audio_url, temp, timeout, medialog):
        stream_runs.append(url)
        temp.write_bytes(b"\0" * 2048)

    async def ok(*a, **k):
        return None

    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_copy_stream", fake_copy)
    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_integrity_check", ok)
    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_check_complete", ok, raising=False)
    downloaded = set()
    monkeypatch.setattr(filters, "get_media_ids_downloaded", lambda **kw: list(downloaded))
    monkeypatch.setattr(filters.separate, "seperate_avatars", lambda m: m)

    def one_run():
        todo = filters.previous_download_filter([make_ele(raw)], username="a-creator",
                                                model_id=100000000000000002)
        results = [asyncio.run(run_download(session, ele)) for ele in todo]
        downloaded.update(mark_id for mark_id, kw in env.marks if kw["downloaded"])
        return results

    assert one_run() == [("Videos", 2048)]
    assert len(stream_runs) == 1 and len(session.calls) == 1
    assert one_run() == []
    assert len(stream_runs) == 1 and len(session.calls) == 1
    assert files_in(env.out) == [f"{make_ele(raw).filename}.mp4"]


# ------------------------------------------------------------------ review fixes

def media_playlist(names):
    body = "#EXTM3U\n#EXT-X-VERSION:4\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-TARGETDURATION:1\n"
    body += "".join(f"#EXTINF:1.000000,\n{n}\n" for n in names)
    return (body + "#EXT-X-ENDLIST\n").encode()


def make_segments(tmp_path, name, *args, source=None):
    """{file name: bytes} of 1-second MPEG-TS segments made by ffmpeg."""
    seg_dir = tmp_path / name
    seg_dir.mkdir()
    ffmpeg_make([*args, "-f", "segment", "-segment_time", "1", "-segment_format", "mpegts",
                 f"{name}-%d.ts"], seg_dir, source)
    return {p.name: p.read_bytes() for p in sorted(seg_dir.glob(f"{name}-*.ts"))}


def serve_hls(srv, raw, master, playlists):
    """Point the HLS variant at ``srv``; ``playlists`` maps a folder under the
    master to its segments. Returns the folder of the master."""
    url = point_at(raw["media"], video.HLS_MIME, srv.base)
    root = urlparse(url).path.rsplit("/", 1)[0]
    srv.files[urlparse(url).path] = master.encode()
    for folder, segments in playlists.items():
        srv.files[f"{root}/{folder}/media.m3u8"] = media_playlist(list(segments))
        srv.files.update({f"{root}/{folder}/{n}": b for n, b in segments.items()})
    return root


def download_locally(ele):
    async def go():
        async with ofsession.download_session() as c:
            return await run_download(c, ele)

    return asyncio.run(go())


VIDEO_ONLY_MASTER = (
    "#EXTM3U\n#EXT-X-VERSION:4\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=9000000,RESOLUTION=3840x2160,CODECS="avc1.640033"\n'
    "r2160/media.m3u8\n"
)
SPLIT_AUDIO_MASTER = (
    "#EXTM3U\n#EXT-X-VERSION:4\n"
    '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Main",DEFAULT=YES,AUTOSELECT=YES,URI="audio/media.m3u8"\n'
    # video-only CODECS: the sound is only in the separate track
    '#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=640x360,CODECS="avc1.64001e",AUDIO="aud"\n'
    "r360/media.m3u8\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=9000000,RESOLUTION=3840x2160,CODECS="avc1.640033",AUDIO="aud"\n'
    "r2160/media.m3u8\n"
)
# Fansly's usual master: the renditions carry the sound (mp4a) and an audio
# group lists a copy of it, which the CDN refuses for some older videos
IN_BAND_AUDIO_MASTER = SPLIT_AUDIO_MASTER.replace('CODECS="avc1.64001e"', 'CODECS="avc1.64001e,mp4a.40.2"').replace(
    'CODECS="avc1.640033"', 'CODECS="avc1.640033,mp4a.40.2"')


def ffmpeg_only(monkeypatch):
    """Leave the stream to ffmpeg alone, as with FANSLY_STREAM_SEGMENTS=0."""
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 0)


def fast_retries(monkeypatch, attempts=2):
    """The download retries without their waits."""
    from tenacity import stop_after_attempt, wait_none

    real = stream_mod.download_retry
    monkeypatch.setattr(stream_mod, "download_retry",
                        lambda: real(stop=stop_after_attempt(attempts), wait=wait_none()))


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("mode", ["stall", "trickle"])
def test_stalled_stream_fails_in_bounded_time_and_leaves_no_part(env, tmp_path, monkeypatch, mode):
    ffmpeg_only(monkeypatch)
    # "stall": the media playlist goes silent and ffmpeg's read timeout ends
    # the run. "trickle": a segment never goes quite silent and the overall
    # time limit ends it. (A segment that goes silent part-way is skipped by
    # ffmpeg's HLS reader without an error; see the PR's known gaps.)
    monkeypatch.setattr(stream_mod, "get_chunk_timeout", lambda: 2)
    # each case passes only through its own limit: the other is set too long
    monkeypatch.setattr(stream_mod, "STREAM_TIMEOUT_FLOOR", 60 if mode == "stall" else 6)
    if mode == "trickle":
        monkeypatch.setattr(stream_mod, "get_chunk_timeout", lambda: 30)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}, slow_limit=40) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        slow_path = "media.m3u8" if mode == "stall" else "segment-1.ts"
        srv.slow[f"{root}/r2160/{slow_path}"] = mode
        ele = make_ele(raw)
        started = time.monotonic()
        result = download_locally(ele)
        elapsed = time.monotonic() - started
    assert elapsed < 25
    assert result == ("skipped", 0)
    assert files_in(env.out, env.temp) == []
    assert env.marks == [] and len(env.ffmpeg_runs) == 1
    assert env.ffmpeg_procs[0].proc.poll() is not None


@needs_ffmpeg
def test_cancelled_download_stops_ffmpeg_and_removes_the_part(env, tmp_path, monkeypatch):
    ffmpeg_only(monkeypatch)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}, slow_limit=40) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        srv.slow[f"{root}/r2160/segment-2.ts"] = "trickle"
        ele = make_ele(raw)

        async def go():
            async with ofsession.download_session() as c:
                task = asyncio.ensure_future(run_download(c, ele))
                deadline = time.monotonic() + 20
                while not any(env.temp.glob("*.part")) and time.monotonic() < deadline:
                    await asyncio.sleep(0.1)
                assert any(env.temp.glob("*.part")), "ffmpeg never started writing"
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

        asyncio.run(go())
    assert files_in(env.out, env.temp) == []
    assert env.marks == []
    assert env.ffmpeg_procs[0].proc.poll() is not None


@needs_ffmpeg
def test_separate_audio_rendition_is_downloaded_with_the_video(env, tmp_path):
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, SPLIT_AUDIO_MASTER,
                         {"r2160": video_segments, "audio": audio_segments})
        ele = make_ele(raw)
        result = download_locally(ele)

    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert files_in(env.out, env.temp) == [out.name]
    assert sorted(s["codec_type"] for s in probe(out)["streams"]) == ["audio", "video"]
    requested = [p for p, _ in srv.seen]
    assert f"{root}/audio/media.m3u8" in requested
    assert all(f"{root}/audio/{n}" in requested for n in audio_segments)
    assert not any("/r360/" in p for p in requested)
    for _, headers in srv.seen:
        assert_cdn_request(headers)
    # fetched in parallel, then one ffmpeg run joins the local video and audio
    (join,) = env.ffmpeg_runs
    assert join.count("-i") == 2 and ["-map", "0:v", "-map", "1:a"] == join[-9:-5]
    assert join[join.index("-protocol_whitelist") + 1] == "file,crypto"
    assert not any("http" in str(a) for a in join)


@needs_ffmpeg
def test_audio_inside_the_video_is_used_and_the_copy_is_not_fetched(env, tmp_path):
    # Fansly's playlists list an audio track the CDN refuses for some older
    # videos; the video segments carry the same sound, as on its website
    segments = make_segments(tmp_path, "v", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, IN_BAND_AUDIO_MASTER, {"r2160": segments})
        ele = make_ele(raw)
        result = download_locally(ele)

    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert sorted(s["codec_type"] for s in probe(out)["streams"]) == ["audio", "video"]
    assert not any("/audio/" in p for p, _ in srv.seen)
    (join,) = env.ffmpeg_runs
    assert join.count("-i") == 1 and "-map" not in join


@needs_ffmpeg
def test_video_without_the_audio_its_playlist_lists_is_saved_and_logged(env, tmp_path, caplog):
    # the playlist says the segments carry sound but they don't: keep the
    # video, as the website plays it, and log why it is silent
    segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, IN_BAND_AUDIO_MASTER, {"r2160": segments})
        # no direct file to take the sound from
        ele = make_ele(raw, direct=False)
        with caplog.at_level(logging.WARNING):
            result = download_locally(ele)
    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert [s["codec_type"] for s in probe(out)["streams"]] == ["video"]
    assert "segments have no audio" in caplog.text and "without sound" in caplog.text


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("refused", ["playlist", "segment"])
def test_refused_audio_track_saves_the_video_and_logs_why(env, tmp_path, caplog, refused):
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, SPLIT_AUDIO_MASTER,
                         {"r2160": video_segments, "audio": audio_segments})
        target = (f"{root}/audio/media.m3u8" if refused == "playlist"
                  else f"{root}/audio/{next(iter(audio_segments))}")
        srv.refuse.add(target)
        # no direct file to take the sound from
        ele = make_ele(raw, direct=False)
        with caplog.at_level(logging.WARNING):
            result = download_locally(ele)
    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert files_in(env.out, env.temp) == [out.name]
    assert [s["codec_type"] for s in probe(out)["streams"]] == ["video"]
    assert "refused" in caplog.text and "without sound" in caplog.text
    assert len(env.marks) == 1
    assert len(env.ffmpeg_runs) == 1


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("case", ["accepted_after_refresh", "refused_again", "no_direct_file"])
def test_a_refused_video_segment_gets_new_links_then_the_direct_file(
        env, tmp_path, monkeypatch, case):
    segments = make_segments(tmp_path, "v", "-bsf:v", "dump_extra=freq=keyframe")
    first, refused = list(segments)[:2]
    raw = raw_media()
    calls, asked = [], []

    async def main_download(self, c, ele, username, model_id):
        calls.append(ele.url)
        return "Videos", 10

    fast_retries(monkeypatch, attempts=1)
    # one file at a time: the first is fetched before the second is refused
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 1)
    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    with Server({}) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        srv.refuse.add(f"{root}/r2160/{refused}")

        async def refresh_media_link(ele):
            asked.append(ele.id)
            if case == "accepted_after_refresh":
                srv.refuse.clear()
            return True

        monkeypatch.setattr(stream_mod, "refresh_media_link", refresh_media_link)
        ele = make_ele(raw, direct=case != "no_direct_file")
        result = download_locally(ele)
    # new links once (#536), as for a refused playlist
    assert asked == [ele.id]
    seen = [path for path, _ in srv.seen]
    if case == "accepted_after_refresh":
        # the stream at its quality, with the file fetched before the refusal kept
        assert result[0] == "Videos" and calls == []
        assert files_in(env.out) == [f"{ele.filename}.mp4"]
        assert len(env.marks) == 1 and len(env.ffmpeg_runs) == 1
        assert seen.count(f"{root}/r2160/{first}") == 1
        assert files_in(env.temp) == []
        return
    assert env.ffmpeg_runs == [] and env.marks == []
    if case == "refused_again":
        assert result == ("Videos", 10)
        assert calls == [ele.url] and ele.url
        # the stream's segments are no use to the direct file
        assert files_in(env.out, env.temp) == []
    else:
        # nothing to fall back to: the item fails as before, and the
        # fetched segments stay for the next run to resume from
        assert result == ("skipped", 0) and calls == []
        assert files_in(env.out) == [] and not list(env.temp.glob("*.part"))
        folder = next(env.temp.glob(".*.segments"))
        kept = [p for p in folder.iterdir() if p.suffix == ".ts"]
        assert [p.read_bytes() for p in kept] == [segments[first]]


# ------------------------------------------------------------------ sound from the direct file

def serve_direct(srv, raw, tmp_path, *args, path=None):
    """Serve a direct MP4 made by ffmpeg (``args`` before its name) at the
    direct file's path, or at ``path``. Returns the path."""
    folder = tmp_path / f"direct{len(srv.files)}"
    folder.mkdir()
    ffmpeg_make([*args, "direct.mp4"], folder)
    loc = next(loc for loc in raw["media"]["locations"] if str(loc["locationId"]) == "1")
    path = path or urlparse(loc["location"]).path
    srv.files[path] = (folder / "direct.mp4").read_bytes()
    return path


def refused_audio_download(env, tmp_path, caplog, direct_args=("-s", "80x60"),
                           refused="segment", setup=None, video_args=(), source=None):
    video_segments = make_segments(tmp_path, "v", "-an", *video_args,
                                   "-bsf:v", "dump_extra=freq=keyframe", source=source)
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, SPLIT_AUDIO_MASTER,
                         {"r2160": video_segments, "audio": audio_segments})
        srv.refuse.add(f"{root}/audio/media.m3u8" if refused == "playlist"
                       else f"{root}/audio/{next(iter(audio_segments))}")
        direct_path = serve_direct(srv, raw, tmp_path, *direct_args) if direct_args else None
        ele = make_ele(raw)
        if setup:
            setup(srv, raw, ele, direct_path)
        with caplog.at_level(logging.INFO):
            result = download_locally(ele)
    out = env.out / f"{ele.filename}.mp4"
    return SimpleNamespace(result=result, out=out, srv=srv, ele=ele, direct=direct_path)


def video_size(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return tuple(int(x) for x in out.split(","))


def warnings_in(caplog):
    return " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("refused", ["playlist", "segment"])
def test_refused_audio_is_taken_from_the_direct_file(env, tmp_path, caplog, refused):
    run = refused_audio_download(env, tmp_path, caplog, refused=refused)
    assert run.result[0] == "Videos" and run.result[1] > 0
    assert files_in(env.out, env.temp) == [run.out.name]
    # the stream's video (160x120), the direct file's (80x60) sound
    assert sorted(s["codec_type"] for s in probe(run.out)["streams"]) == ["audio", "video"]
    assert video_size(run.out) == (160, 120)
    assert "without sound" not in warnings_in(caplog)
    assert "took the sound from the direct file" in caplog.text
    # the direct file is fetched with no CDN cookies: its link is signed
    direct_requests = [h for p, h in run.srv.seen if p == run.direct]
    assert len(direct_requests) == 1 and "cookie" not in direct_requests[0]
    join, borrow = env.ffmpeg_runs
    assert borrow[-9:-5] == ["-map", "0:v", "-map", "1:a:0"]
    assert len(env.marks) == 1


@pytest.mark.slow
@needs_ffmpeg
def test_a_direct_file_without_sound_saves_the_stream_as_it_is(env, tmp_path, caplog):
    run = refused_audio_download(env, tmp_path, caplog, direct_args=("-s", "80x60", "-an"))
    assert run.result[0] == "Videos"
    assert [s["codec_type"] for s in probe(run.out)["streams"]] == ["video"]
    assert warnings_in(caplog) == ""
    assert "has no sound either" in caplog.text
    assert len(env.ffmpeg_runs) == 1


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("times", [1, 2])
def test_a_refused_direct_file_gets_a_new_link_once(env, tmp_path, caplog, monkeypatch, times):
    asked = []

    def setup(srv, raw, ele, direct_path):
        srv.refuse.add(direct_path)
        new_path = direct_path.replace(".mp4", "-new.mp4")
        srv.files[new_path] = srv.files[direct_path]
        if times == 2:
            srv.refuse.add(new_path)

        async def refresh_media_link(ele):
            asked.append(ele.id)
            ele.url = ele.url.replace(direct_path, new_path)
            return True

        monkeypatch.setattr(stream_mod, "refresh_media_link", refresh_media_link)

    fast_retries(monkeypatch, attempts=1)
    run = refused_audio_download(env, tmp_path, caplog, setup=setup)
    assert run.result[0] == "Videos"
    assert len(asked) == 1
    kinds = sorted(s["codec_type"] for s in probe(run.out)["streams"])
    if times == 1:
        assert kinds == ["audio", "video"]
        assert "without sound" not in warnings_in(caplog)
    else:
        assert kinds == ["video"]
        assert "without sound" in warnings_in(caplog)


@pytest.mark.slow
@needs_ffmpeg
def test_a_direct_file_of_another_length_is_not_used(env, tmp_path, caplog):
    run = refused_audio_download(env, tmp_path, caplog, direct_args=("-s", "80x60", "-t", "2"))
    assert run.result[0] == "Videos"
    assert [s["codec_type"] for s in probe(run.out)["streams"]] == ["video"]
    assert "out of step" in caplog.text and "without sound" in warnings_in(caplog)
    assert files_in(env.out, env.temp) == [run.out.name]


@pytest.mark.slow
@needs_ffmpeg
def test_a_copy_with_the_direct_sound_that_fails_the_check_is_discarded(env, tmp_path, caplog, monkeypatch):
    real = video.incomplete_reason

    def holes_with_sound(video_times, audio_times=None, expected=None):
        return "a hole" if audio_times else real(video_times, audio_times, expected)

    monkeypatch.setattr(video, "incomplete_reason", holes_with_sound)
    run = refused_audio_download(env, tmp_path, caplog)
    assert run.result[0] == "Videos"
    assert [s["codec_type"] for s in probe(run.out)["streams"]] == ["video"]
    assert "incomplete: a hole" in caplog.text and "without sound" in warnings_in(caplog)
    assert files_in(env.out, env.temp) == [run.out.name]


def direct_bytes(tmp_path, *args):
    """A direct file made by ffmpeg from ``args`` (inputs and options)."""
    folder = tmp_path / "custom-direct"
    folder.mkdir(exist_ok=True)
    out = folder / "direct.mp4"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args, str(out)],
                   check=True)
    return out.read_bytes()


def with_direct(data):
    def setup(srv, raw, ele, direct_path):
        srv.files[direct_path] = data

    return setup


TEST_VIDEO = ["-f", "lavfi", "-i", "testsrc=size=80x60:rate=10:duration=3"]


def sine(seconds):
    return ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]


def kinds_of(path):
    return sorted(s["codec_type"] for s in probe(path)["streams"])


def saved_silent_with_warning(run, caplog, why):
    assert run.result[0] == "Videos" and run.result[1] > 0
    assert kinds_of(run.out) == ["video"]
    assert why in caplog.text
    # the refusal warning: the later re-check (silent.py) looks for it
    assert "without sound" in warnings_in(caplog)


@pytest.mark.slow
@needs_ffmpeg
def test_a_direct_file_that_cannot_be_read_is_not_taken_for_silence(env, tmp_path, caplog):
    # an error page where the file should be says nothing about the sound
    run = refused_audio_download(
        env, tmp_path, caplog, setup=with_direct(b"<html>temporarily unavailable</html>")
    )
    saved_silent_with_warning(run, caplog, "could not be read to check its sound")
    assert "has no sound either" not in caplog.text


def video_after_sound(path):
    """Seconds the first frame is shown after the sound starts."""
    return (stream_mod._first_shown(FFPROBE, path, "v:0")
            - stream_mod._first_shown(FFPROBE, path, "a:0"))


def flash_source(rate, at=1, seconds=3):
    """ffmpeg inputs: a black picture that turns white and silence that
    turns into a tone, both ``at`` seconds in."""
    return [
        "-f", "lavfi", "-i",
        f"color=c=black:s=160x120:r={rate}:d={seconds},"
        f"drawbox=w=iw:h=ih:color=white:t=fill:enable='gte(t,{at})'",
        "-f", "lavfi", "-i",
        f"aevalsrc='0.5*sin(2*PI*1000*t)*gte(t,{at})':d={seconds}:s=44100",
    ]


def picture_after_sound(path, tmp_path):
    """Seconds the picture turns white after the tone starts, as ``path``
    plays (decoded): what a viewer sees of its sync."""
    plain = tmp_path / "measured.mp4"
    shutil.copy(path, plain)

    def first(graph, tag, found):
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-f", "lavfi", graph, "-show_entries",
             f"frame=pts_time:frame_tags={tag}", "-of", "csv=p=0"],
            cwd=tmp_path, check=True, capture_output=True, text=True,
        ).stdout
        for line in out.splitlines():
            parts = line.strip().strip(",").split(",")
            if len(parts) > 1 and parts[1] not in ("", "-inf") and found(float(parts[1])):
                return float(parts[0])
        raise AssertionError(f"nothing found in {path.name}")

    flash = first(f"movie={plain.name},signalstats", "lavfi.signalstats.YAVG",
                  lambda level: level > 128)
    tone = first(f"amovie={plain.name},asetnsamples=n=48,astats=metadata=1:reset=1",
                 "lavfi.astats.Overall.Peak_level", lambda level: level > -20)
    return flash - tone


@pytest.mark.slow
@needs_ffmpeg
def test_a_video_that_starts_long_after_its_sound_is_not_used(env, tmp_path, caplog):
    # by half a second: more than frames stored ahead explain, and nothing
    # shows that the stream's video starts as late
    data = direct_bytes(tmp_path, "-itsoffset", "0.5", *TEST_VIDEO, *sine(3),
                        "-c:v", "mpeg4", "-g", "10", "-c:a", "aac")
    run = refused_audio_download(env, tmp_path, caplog, setup=with_direct(data))
    saved_silent_with_warning(run, caplog, "out of step")


def test_times_of_packets_marked_as_not_played_are_left_out():
    out = "-0.023220,KD_\n0.000000,K__\n0.023220,K__\nN/A,K__\n\n"
    assert stream_mod._read_times(out) == [-0.02322, 0.0, 0.02322]
    assert stream_mod._read_times(out, played=True) == [0.0, 0.02322]
    # ffprobe without a flags column
    assert stream_mod._read_times("0.5\n1.0,\n", played=True) == [0.5, 1.0]


@pytest.mark.slow
@needs_ffmpeg
def test_packets_the_file_marks_as_hidden_do_not_count(env, tmp_path, caplog, rate=44100):
    # 60 fps video with AAC sound, as phones record it. An MP4 keeps the
    # encoder's lead-in packet and marks it as not played; counted, it makes
    # the sound look longer than the video by more than two short frames
    data = direct_bytes(
        tmp_path, "-f", "lavfi", "-i", "testsrc=size=80x60:rate=60:duration=3",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration=3:sample_rate={rate}",
        "-c:v", "mpeg4", "-g", "60", "-c:a", "aac",
    )
    run = refused_audio_download(
        env, tmp_path, caplog, setup=with_direct(data), video_args=("-r", "60", "-g", "60"),
    )
    assert "longer than" not in caplog.text and "out of step" not in caplog.text
    assert kinds_of(run.out) == ["audio", "video"]
    assert "without sound" not in warnings_in(caplog)


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("cut", [1, 7], ids=["a-short-cut", "a-cut-deeper-than-64-frames"])
def test_a_direct_file_cut_without_re_encoding_is_used(env, tmp_path, caplog, cut):
    # cut with -ss and -c copy: the file keeps the frames back to the key
    # frame before the cut (10 or 70 here) and marks them as not played. The
    # start of its video is the first frame that is played
    whole = tmp_path / "whole.mp4"
    subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
         *flash_source(10, at=cut + 1, seconds=cut + 3),
         "-c:v", "mpeg4", "-g", "250", "-c:a", "aac", str(whole)],
        check=True,
    )
    direct = tmp_path / "cut.mp4"
    direct.write_bytes(direct_bytes(tmp_path, "-ss", str(cut), "-i", str(whole), "-c", "copy"))
    run = refused_audio_download(
        env, tmp_path, caplog, setup=with_direct(direct.read_bytes()), source=flash_source(10)
    )
    assert "could not be measured" not in caplog.text and "out of step" not in caplog.text
    assert kinds_of(run.out) == ["audio", "video"]
    assert "without sound" not in warnings_in(caplog)
    # the cut falls inside a sound packet (11 ms into it at 7 s): the sound
    # starts at the cut, not at that packet's time
    assert picture_after_sound(run.out, tmp_path) == pytest.approx(
        picture_after_sound(direct, tmp_path), abs=0.005
    )


def has_encoder(name):
    if not FFMPEG:
        return False
    out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True)
    return f" {name} " in out.stdout


needs_x264 = pytest.mark.skipif(not has_encoder("libx264"), reason="ffmpeg has no libx264")


def first_sound_packet(path):
    """Seconds the first sound packet lasts."""
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a:0", "-read_intervals", "%+#1",
         "-show_entries", "packet=duration_time", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(out.split()[0].strip(","))


def stored_ahead(tmp_path, source, rate, shape="ffmpeg"):
    """A direct file as Fansly's usually are: frames stored ahead of the
    ones shown before them and no edit list, so the first frame is shown two
    frames after the sound starts.

    ``ffmpeg``: as ffmpeg writes it, in one go. It makes the first sound
    packet two frames longer, so the sound is in step and longer than the
    video. ``saved``: as the saved Fansly videos sampled are, with a first
    sound packet of normal length (the two tracks written apart, then joined
    with their times kept)."""
    codecs = ["-c:v", "libx264", "-bf", "2", "-g", str(rate), "-c:a", "aac"]
    direct = tmp_path / "ahead.mp4"
    if shape == "ffmpeg":
        direct.write_bytes(direct_bytes(tmp_path, *source, *codecs, "-use_editlist", "0"))
        assert first_sound_packet(direct) > 0.028
    else:
        for name, only in (("v.mp4", "-an"), ("a.mp4", "-vn")):
            (tmp_path / name).write_bytes(
                direct_bytes(tmp_path, *source, *codecs, only, "-use_editlist", "0")
            )
        direct.write_bytes(direct_bytes(
            tmp_path, "-copyts", "-i", str(tmp_path / "v.mp4"), "-i", str(tmp_path / "a.mp4"),
            "-map", "0:v", "-map", "1:a", "-c", "copy", "-use_editlist", "0",
        ))
        assert first_sound_packet(direct) < 0.028
    assert video_after_sound(direct) == pytest.approx(2 / rate, abs=0.002)
    return direct


@needs_ffmpeg
@needs_x264
@pytest.mark.parametrize(
    "shape, rate", [("ffmpeg", 24), ("ffmpeg", 30), ("ffmpeg", 60), ("saved", 30), ("saved", 60)]
)
@pytest.mark.slow
def test_frames_stored_ahead_with_no_edit_list_keep_the_direct_files_sync(
    env, tmp_path, caplog, shape, rate
):
    source = flash_source(rate)
    direct = stored_ahead(tmp_path, source, rate, shape)
    run = refused_audio_download(
        env, tmp_path, caplog, setup=with_direct(direct.read_bytes()), source=source,
        video_args=("-g", str(rate)),
    )
    assert "longer than" not in caplog.text and "out of step" not in caplog.text
    assert kinds_of(run.out) == ["audio", "video"]
    assert "without sound" not in warnings_in(caplog)
    # the stream's video starts as late after the sound as the direct file's,
    # and the picture is where it was against the sound
    assert video_after_sound(run.out) == pytest.approx(2 / rate, abs=0.002)
    assert picture_after_sound(run.out, tmp_path) == pytest.approx(
        picture_after_sound(direct, tmp_path), abs=0.005
    )


@pytest.mark.slow
@needs_ffmpeg
@needs_x264
def test_a_joined_copy_whose_sound_moved_against_the_video_is_not_used(
    env, tmp_path, caplog, monkeypatch
):
    # the check on the result: a join that lost the video's start is refused
    real = video.local_join_command

    def no_delay(*args, video_delay=0.0, **kwargs):
        return real(*args, **kwargs)

    monkeypatch.setattr(video, "local_join_command", no_delay)
    direct = stored_ahead(tmp_path, [*TEST_VIDEO, *sine(3)], 10)
    run = refused_audio_download(env, tmp_path, caplog, setup=with_direct(direct.read_bytes()))
    saved_silent_with_warning(run, caplog, "so it would be out of step")


@needs_ffmpeg
@needs_x264
@pytest.mark.parametrize(
    "direct, stream",
    [(["-bf", "3"], ["-bf", "0"]), (["-bf", "0"], ["-bf", "3"])],
    ids=["b-frames-in-the-direct-file", "b-frames-in-the-stream"],
)
@pytest.mark.slow
def test_frames_stored_in_another_order_do_not_read_as_an_offset(
    env, tmp_path, caplog, direct, stream
):
    # B-frames are stored ahead of the frames shown before them, so a stream's
    # first stored time is earlier than its first shown one, by an amount set
    # by the encoder's options. The two copies of one upload are encoded
    # separately; both here are in step.
    data = direct_bytes(tmp_path, *TEST_VIDEO, *sine(3), "-c:v", "libx264", *direct,
                        "-g", "10", "-c:a", "aac", "-shortest")
    run = refused_audio_download(
        env, tmp_path, caplog, setup=with_direct(data),
        video_args=("-c:v", "libx264", *stream, "-g", "10"),
    )
    assert "out of step" not in caplog.text
    assert kinds_of(run.out) == ["audio", "video"]
    assert "without sound" not in warnings_in(caplog)


def test_the_wait_for_a_new_direct_link_keeps_to_the_time_limit(monkeypatch, tmp_path):
    manager = object.__new__(stream_mod.FanslyStreamDownloadManager)

    async def refused(c, url, path, cookies):
        raise stream_mod.SegmentError("status 403")

    async def never(ele):
        await asyncio.sleep(60)

    monkeypatch.setattr(manager, "_fetch_segment", refused, raising=False)
    monkeypatch.setattr(stream_mod, "_refused", lambda e: True)
    monkeypatch.setattr(stream_mod, "refresh_media_link", never)
    ele = SimpleNamespace(url="https://cdn.invalid/direct.mp4")

    async def go():
        loop = asyncio.get_running_loop()
        started = loop.time()
        with pytest.raises(asyncio.TimeoutError):
            await manager._fetch_direct(None, ele, tmp_path / "direct.mp4", started + 0.2)
        return loop.time() - started

    assert asyncio.run(go()) < 5


@needs_ffmpeg
def test_a_sound_copy_left_by_a_killed_run_is_removed(env, tmp_path):
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, SPLIT_AUDIO_MASTER,
                  {"r2160": video_segments, "audio": audio_segments})
        ele = make_ele(raw)
        left = env.temp / f"{ele.filename}_{ele.id}_{ele.post_id}.part.sound"
        left.write_bytes(b"half a join")
        result = download_locally(ele)
    assert result[0] == "Videos"
    assert files_in(env.out, env.temp) == [f"{ele.filename}.mp4"]


@pytest.mark.slow
@needs_ffmpeg
def test_sound_that_is_not_aac_is_not_used(env, tmp_path, caplog):
    data = direct_bytes(tmp_path, *TEST_VIDEO, *sine(3), "-c:v", "mpeg4", "-g", "10",
                        "-c:a", "mp3", "-shortest")
    run = refused_audio_download(env, tmp_path, caplog, setup=with_direct(data))
    saved_silent_with_warning(run, caplog, "is mp3, not AAC")


@pytest.mark.slow
@needs_ffmpeg
def test_sound_that_covers_part_of_the_video_is_not_used(env, tmp_path, caplog):
    data = direct_bytes(tmp_path, *TEST_VIDEO, *sine(1.5), "-c:v", "mpeg4", "-g", "10",
                        "-c:a", "aac")
    run = refused_audio_download(env, tmp_path, caplog, setup=with_direct(data))
    saved_silent_with_warning(run, caplog, "covers 1.")


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("failure", ["time limit", "ffprobe error", "disk full", "locked file"])
def test_any_failure_while_adding_the_sound_saves_the_silent_copy(
    env, tmp_path, caplog, monkeypatch, failure
):
    if failure == "time limit":
        real = stream_mod.FanslyStreamDownloadManager._run_cmd

        async def run_cmd(self, cmd, temp, timeout, what, cwd=None):
            if what == "add the direct file's sound":
                raise stream_mod.StreamTimeout("ffmpeg ran longer than 1s and was stopped")
            return await real(self, cmd, temp, timeout, what, cwd=cwd)

        monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_run_cmd", run_cmd)
        why = "ran longer"
    elif failure == "ffprobe error":
        async def broken(*a, **k):
            raise subprocess.CalledProcessError(1, "ffprobe")

        monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_sound_mismatch", broken)
        why = "returned non-zero exit status"
    elif failure == "disk full":
        def check(self, temp, direct):
            raise stream_mod.NotEnoughSpace("not enough disk space to add the sound")

        monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_check_sound_space", check)
        why = "not enough disk space to add the sound"
    else:
        real_replace = pathlib.Path.replace

        def replace(self, target):
            if self.name.endswith(".sound"):
                raise PermissionError("the file is in use")
            return real_replace(self, target)

        monkeypatch.setattr(pathlib.Path, "replace", replace)
        why = "the file is in use"
    run = refused_audio_download(env, tmp_path, caplog)
    saved_silent_with_warning(run, caplog, why)
    assert files_in(env.out, env.temp) == [run.out.name]


@needs_ffmpeg
def test_segments_without_their_listed_sound_take_it_from_the_direct_file(env, tmp_path, caplog):
    segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, IN_BAND_AUDIO_MASTER, {"r2160": segments})
        serve_direct(srv, raw, tmp_path, "-s", "80x60")
        ele = make_ele(raw)
        with caplog.at_level(logging.INFO):
            result = download_locally(ele)
    out = env.out / f"{ele.filename}.mp4"
    assert result[0] == "Videos"
    assert sorted(s["codec_type"] for s in probe(out)["streams"]) == ["audio", "video"]
    assert warnings_in(caplog) == ""


def test_the_direct_sound_join_reads_only_local_files_without_hls_options():
    cmd = video.local_join_command("ffmpeg", "video.m3u8", "out.part", audio_file="direct.mp4")
    first, second = [i for i, a in enumerate(cmd) if a == "-i"]
    assert cmd[first + 1] == "video.m3u8" and cmd[second + 1] == "direct.mp4"
    second_opts = cmd[first + 2:second]
    assert second_opts == ["-protocol_whitelist", "file"]
    assert "-allowed_extensions" in cmd[:first]
    assert cmd[second + 2:second + 6] == ["-map", "0:v", "-map", "1:a:0"]
    dash = video.local_join_command("ffmpeg", "video.mp4", "out.part", dash=True,
                                    audio_file="direct.mp4")
    assert "-allowed_extensions" not in dash


# ------------------------------------------------------------------ silent videos checked again

@pytest.fixture
def sound_marks(monkeypatch):
    marks = []
    monkeypatch.setattr(stream_mod.silent, "flag",
                        lambda model_id, ele, path: marks.append(("flag", ele.id, str(path))))
    monkeypatch.setattr(stream_mod.silent, "clear",
                        lambda model_id, media_id: marks.append(("clear", media_id)))
    return marks


@pytest.mark.slow
@needs_ffmpeg
def test_a_video_saved_silent_because_its_audio_was_refused_is_flagged(
        env, tmp_path, caplog, sound_marks):
    run = refused_audio_download(env, tmp_path, caplog, direct_args=None)
    assert [s["codec_type"] for s in probe(run.out)["streams"]] == ["video"]
    assert sound_marks == [("flag", run.ele.id, str(run.out))]


@pytest.mark.slow
@needs_ffmpeg
def test_a_video_with_its_sound_from_the_direct_file_is_not_flagged(
        env, tmp_path, caplog, sound_marks):
    run = refused_audio_download(env, tmp_path, caplog)
    assert sound_marks == [("clear", run.ele.id)]


@needs_ffmpeg
def test_segments_without_their_listed_sound_are_not_flagged(env, tmp_path, sound_marks):
    # nothing can be fetched later: a check could never succeed
    segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, IN_BAND_AUDIO_MASTER, {"r2160": segments})
        ele = make_ele(raw, direct=False)
        download_locally(ele)
    assert sound_marks == [("clear", ele.id)]


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("sound", [True, False])
def test_downloading_a_silent_video_again_replaces_it_only_with_sound(
        env, tmp_path, caplog, sound_marks, sound):
    old = env.out / "saved-earlier.mp4"
    old.write_bytes(b"silent copy")

    def setup(srv, raw, ele, direct_path):
        ele.replace_silent = str(old)
        if sound:
            srv.refuse.clear()

    run = refused_audio_download(env, tmp_path, caplog, direct_args=None, setup=setup)
    if sound:
        assert run.result[0] == "Videos"
        # the copy with sound takes the silent copy's place
        assert files_in(env.out, env.temp) == [old.name]
        assert sorted(s["codec_type"] for s in probe(old)["streams"]) == ["audio", "video"]
        assert sound_marks == [("clear", run.ele.id)]
    else:
        assert run.result == ("skipped", 0)
        assert old.read_bytes() == b"silent copy"
        assert files_in(env.out, env.temp) == [old.name]
        assert sound_marks == []
        # silent.recheck counts this as refused again, not as a failed download
        assert run.ele.still_silent is True


@needs_ffmpeg
@pytest.mark.parametrize("error", [
    PermissionError("the file is in use"),
    OSError(errno.ENOSPC, "No space left on device"),
    FileNotFoundError("the drive is gone"),
], ids=["in-use", "disk-full", "drive-gone"])
@pytest.mark.slow
def test_the_silent_copy_stays_until_the_copy_with_sound_replaces_it(
        env, tmp_path, caplog, sound_marks, monkeypatch, error):
    old = env.out / "saved-earlier.mp4"
    old.write_bytes(b"silent copy")
    seen = []
    real = stream_mod.os.replace

    def replace(src, dst):
        if pathlib.Path(dst) != old:
            return real(src, dst)
        # the new copy is whole beside the silent one, which is still there
        seen.append((pathlib.Path(src).parent == old.parent, old.read_bytes()))
        raise error

    def setup(srv, raw, ele, direct_path):
        ele.replace_silent = str(old)
        srv.refuse.clear()

    monkeypatch.setattr(stream_mod.os, "replace", replace)
    run = refused_audio_download(env, tmp_path, caplog, direct_args=None, setup=setup)
    assert run.result == ("skipped", 0)
    assert seen == [(True, b"silent copy")]
    assert old.read_bytes() == b"silent copy"
    assert files_in(env.out, env.temp) == [old.name]
    # silent.recheck counts a check: the next run would end the same way
    assert "could not be replaced" in run.ele.not_kept


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("skipped_by", ["size", "script", "script-for-good"])
def test_a_copy_with_sound_that_a_filter_skips_leaves_the_silent_copy_and_its_row(
        env, tmp_path, caplog, sound_marks, monkeypatch, skipped_by):
    old = env.out / "saved-earlier.mp4"
    old.write_bytes(b"silent copy")
    forced = []

    async def force_download(self, ele, username, model_id, **kw):
        forced.append(kw)

    async def script(total, ele):
        return dm.SKIP_PERMANENT if skipped_by == "script-for-good" else True

    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_force_download", force_download)
    if skipped_by == "size":
        env.stub.size_max = 10
    else:
        monkeypatch.setattr(dm, "skip_download_script", script)

    def setup(srv, raw, ele, direct_path):
        ele.replace_silent = str(old)
        srv.refuse.clear()

    run = refused_audio_download(env, tmp_path, caplog, direct_args=None, setup=setup)
    assert run.result == ("forced_skipped", 0)
    assert old.read_bytes() == b"silent copy"
    assert files_in(env.out, env.temp) == [old.name]
    # the row keeps the silent copy's file, and its flag stays for the count
    assert forced == [] and env.marks == [] and sound_marks == []
    assert "skipped" in run.ele.not_kept


@needs_ffmpeg
def test_a_silent_copy_moved_away_with_its_folder_gets_the_copy_with_sound_there(
        env, tmp_path, caplog, sound_marks):
    old = env.out / "moved-away" / "saved-earlier.mp4"

    def setup(srv, raw, ele, direct_path):
        ele.replace_silent = str(old)
        srv.refuse.clear()

    run = refused_audio_download(env, tmp_path, caplog, direct_args=None, setup=setup)
    assert run.result[0] == "Videos"
    assert sorted(s["codec_type"] for s in probe(old)["streams"]) == ["audio", "video"]


def test_the_audio_check_tries_a_file_that_carries_sound():
    text = (
        "#EXTM3U\n#EXT-X-VERSION:7\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-TARGETDURATION:1\n"
        '#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n'
        '#EXT-X-MAP:URI="init.mp4"\n'
        "#EXTINF:1.0,\nseg-0.m4s\n#EXTINF:1.0,\nseg-1.m4s\n#EXT-X-ENDLIST\n"
    )
    files = video.local_playlist(text, "https://cdn.example/audio/media.m3u8", "a").files
    assert [url.rsplit("/", 1)[1] for url, _ in files[:2]] == ["key.bin", "init.mp4"]
    assert video.first_media_url(files) == "https://cdn.example/audio/seg-0.m4s"
    assert video.first_media_url(files[:2]) is None


@needs_ffmpeg
def test_the_audio_check_is_not_answered_by_a_setup_file(env, tmp_path):
    # the init segment is served, the sound itself is refused
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    playlist = (
        "#EXTM3U\n#EXT-X-VERSION:7\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-TARGETDURATION:1\n"
        '#EXT-X-MAP:URI="init.mp4"\n#EXTINF:1.0,\nseg-0.m4s\n#EXT-X-ENDLIST\n'
    )
    with Server({}) as srv:
        root = serve_hls(srv, raw, SPLIT_AUDIO_MASTER, {"r2160": video_segments})
        srv.files[f"{root}/audio/media.m3u8"] = playlist.encode()
        srv.files[f"{root}/audio/init.mp4"] = b"init"
        srv.files[f"{root}/audio/seg-0.m4s"] = b"sound"
        srv.refuse.add(f"{root}/audio/seg-0.m4s")

        async def go():
            async with ofsession.download_session() as c:
                return await stream_mod.FanslyStreamDownloadManager().audio_check(c, raw["media"])

        assert asyncio.run(go()) == stream_mod.silent.REFUSED
        requested = [p for p, _ in srv.seen]
    assert f"{root}/audio/init.mp4" not in requested


def test_a_video_saved_from_its_direct_file_needs_no_more_audio_checks(
        env, monkeypatch, sound_marks):
    raw = raw_media()
    url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]

    async def main_download(self, c, ele, username, model_id):
        return "Videos", 10

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    ele = make_ele(raw)
    assert asyncio.run(run_download(FakeSession({url: EMPTY_MASTER}), ele)) == ("Videos", 10)
    assert sound_marks == [("clear", ele.id)]


@needs_ffmpeg
@pytest.mark.parametrize("case, expected", [
    ("accepted", stream_mod.silent.ACCEPTED),
    ("playlist_refused", stream_mod.silent.REFUSED),
    ("file_refused", stream_mod.silent.REFUSED),
    ("file_missing", stream_mod.silent.FAILED),
    # the master playlist says nothing about the audio: no check is used
    ("master_refused", stream_mod.silent.FAILED),
])
@pytest.mark.slow
def test_the_audio_check_asks_for_the_playlist_and_its_first_file(env, tmp_path, case, expected):
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, SPLIT_AUDIO_MASTER,
                         {"r2160": video_segments, "audio": audio_segments})
        first = f"{root}/audio/{next(iter(audio_segments))}"
        if case == "playlist_refused":
            srv.refuse.add(f"{root}/audio/media.m3u8")
        elif case == "file_refused":
            srv.refuse.add(first)
        elif case == "file_missing":
            del srv.files[first]
        elif case == "master_refused":
            srv.refuse.add(next(p for p in srv.files if p.startswith(root) and p.count("/") == root.count("/") + 1))

        async def go():
            async with ofsession.download_session() as c:
                return await stream_mod.FanslyStreamDownloadManager().audio_check(c, raw["media"])

        assert asyncio.run(go()) == expected
        requested = [p for p, _ in srv.seen]
    # two small requests after the master: no video segment is fetched
    assert not any("/r2160/" in p and p.endswith(".ts") for p in requested)
    if case == "master_refused":
        assert first not in requested
    elif case != "playlist_refused":
        assert requested.count(first) == 1


@needs_ffmpeg
def test_audio_track_that_fails_for_another_reason_still_fails_the_file(env, tmp_path, monkeypatch):
    # a 404 or a dropped connection may work next run: don't save it silent
    fast_retries(monkeypatch, attempts=2)
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, SPLIT_AUDIO_MASTER,
                         {"r2160": video_segments, "audio": audio_segments})
        srv.fail[f"{root}/audio/{next(iter(audio_segments))}"] = 99
        result = download_locally(make_ele(raw))
    assert result == ("skipped", 0)
    assert list(env.out.iterdir()) == [] and env.marks == []


def test_audio_codecs_in_a_rendition_mean_its_segments_carry_the_sound():
    base = "https://cdn3.fansly.com/new/1/2/2.m3u8"
    assert video.best_rendition_info(IN_BAND_AUDIO_MASTER, base) == (
        "https://cdn3.fansly.com/new/1/2/r2160/media.m3u8", None, True)
    assert video.best_rendition_info(SPLIT_AUDIO_MASTER, base)[2] is False
    assert video.best_rendition_info(VIDEO_ONLY_MASTER, base) == (
        "https://cdn3.fansly.com/new/1/2/r2160/media.m3u8", None, False)
    for codecs in ("avc1.640033,mp4a.40.2", "hvc1.1.6.L93.B0, ec-3", "avc1.64001f,Opus"):
        assert video._has_audio(codecs)
    for codecs in ("avc1.640033", "", "hvc1.1.6.L93.B0"):
        assert not video._has_audio(codecs)


def test_audio_group_is_resolved_from_the_master():
    base = "https://cdn3.fansly.com/new/1/2/2.m3u8"
    assert video.best_rendition(SPLIT_AUDIO_MASTER, base) == (
        "https://cdn3.fansly.com/new/1/2/r2160/media.m3u8",
        "https://cdn3.fansly.com/new/1/2/audio/media.m3u8",
    )
    # no URI: the audio is inside the rendition (RFC 8216 4.3.4.2.1)
    in_band = SPLIT_AUDIO_MASTER.replace(',URI="audio/media.m3u8"', "")
    assert video.best_rendition(in_band, base)[1] is None
    # the DEFAULT rendition of the group wins
    two = SPLIT_AUDIO_MASTER.replace(
        "#EXT-X-MEDIA:", '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Alt",DEFAULT=NO,URI="alt.m3u8"\n#EXT-X-MEDIA:', 1)
    assert video.best_rendition(two, base)[1].endswith("/audio/media.m3u8")
    cmd = video.ffmpeg_command("ffmpeg", "https://x/v.m3u8", "out.part", {}, {},
                               audio_url="https://x/a.m3u8")
    assert cmd[cmd.index("-map"):cmd.index("-c")] == ["-map", "0:v", "-map", "1:a"]
    assert cmd.count("-i") == 2


def test_unlisted_audio_group_fails_instead_of_saving_a_silent_video(env):
    raw = raw_media()
    hls_url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
    master = SPLIT_AUDIO_MASTER.replace('GROUP-ID="aud"', 'GROUP-ID="other"')
    session = FakeSession({hls_url: master})
    with pytest.raises(video.MissingAudio):
        asyncio.run(stream_mod.FanslyStreamDownloadManager().stream_download(
            session, make_ele(raw, direct=False), "a-creator", 100000000000000002))
    assert files_in(env.out, env.temp) == []
    assert env.ffmpeg_runs == [] and env.marks == []


def test_ffmpeg_gets_a_read_timeout_and_a_protocol_whitelist(monkeypatch):
    cmd = video.ffmpeg_command("ffmpeg", "https://x/v.m3u8", "out.part", {"User-Agent": UA}, {},
                               audio_url="https://x/a.m3u8", rw_timeout=30)
    first, second = [i for i, a in enumerate(cmd) if a == "-i"]
    for start, end in ((0, first), (first + 2, second)):
        opts = cmd[start:end]
        assert opts[opts.index("-rw_timeout") + 1] == "30000000"
        assert opts[opts.index("-protocol_whitelist") + 1] == "https,tls,tcp,crypto"
    assert stream_mod.stream_timeout(None) == stream_mod.STREAM_TIMEOUT_FLOOR
    assert stream_mod.stream_timeout(7200) == 7200 * stream_mod.STREAM_TIMEOUT_PER_SECOND


def test_non_https_stream_urls_are_refused(env, monkeypatch):
    monkeypatch.setattr(video, "ALLOWED_SCHEMES", ("https",))
    for url in ("http://cdn.example/a.m3u8", "file:///etc/passwd", "ftp://x/a.m3u8", ""):
        with pytest.raises(video.StreamError):
            video.check_url(url)
    assert video.check_url("https://cdn.example/a.m3u8")
    raw = raw_media()
    hls_url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
    for master in (MASTER.replace("r2160/media.m3u8", "file:///etc/passwd"),
                   SPLIT_AUDIO_MASTER.replace('URI="audio/media.m3u8"', 'URI="http://cdn.example/a.m3u8"')):
        session = FakeSession({hls_url: master})
        assert asyncio.run(run_download(session, make_ele(raw, direct=False))) == ("skipped", 0)
    assert env.ffmpeg_runs == [] and files_in(env.out, env.temp) == []


def test_line_breaks_are_removed_from_header_and_cookie_values():
    cmd = video.ffmpeg_command(
        "ffmpeg", "https://x/v.m3u8", "out.part",
        {"User-Agent": "UA\r\nX-Injected: 1", "Referer": "https://fansly.com/\nX-Other: 2"},
        {"CloudFront-Policy": "P\r\nX-Cookie: 3"},
    )
    ua = cmd[cmd.index("-user_agent") + 1]
    headers = cmd[cmd.index("-headers") + 1]
    assert "\r" not in ua and "\n" not in ua
    assert headers.count("\r\n") == 2  # Referer and Cookie, nothing else
    assert all(not line.startswith("X-") for line in headers.split("\r\n"))


@pytest.mark.parametrize("case", ["protected_dash", "empty_master", "manifest_404", "manifest_403"])
def test_unusable_stream_falls_back_to_the_direct_file(env, monkeypatch, case):
    raw = raw_media()
    if case == "protected_dash":
        raw = drop_variant(raw, video.HLS_MIME)
        url = variant(raw["media"], video.DASH_MIME)["locations"][0]["location"]
        bodies = {url: PROTECTED_MPD}
    else:
        url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
        bodies = {"empty_master": {url: EMPTY_MASTER}, "manifest_404": {},
                  "manifest_403": {url: RuntimeError("403, message=Forbidden")}}[case]
    calls = []

    async def main_download(self, c, ele, username, model_id):
        calls.append(ele.url)
        return "Videos", 10

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    ele = make_ele(raw)
    assert asyncio.run(run_download(FakeSession(bodies), ele)) == ("Videos", 10)
    assert calls == [ele.url] and ele.url
    assert env.ffmpeg_runs == [] and files_in(env.out, env.temp) == []


def _refused(url):
    info = aiohttp.RequestInfo(URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url))
    return aiohttp.ClientResponseError(info, (), status=403)


@pytest.mark.parametrize("refreshed", [True, False])
def test_a_refused_playlist_is_fetched_again_with_new_links(env, monkeypatch, refreshed):
    # Fansly sometimes signs the links for another address (#683)
    raw = raw_media()
    old_url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
    new_url = old_url.replace(".m3u8", "-new.m3u8")
    session = FakeSession({old_url: _refused(old_url), new_url: EMPTY_MASTER})
    asked = []

    async def refresh_media_link(ele):
        asked.append(ele.id)
        if not refreshed:
            return False
        new = copy.deepcopy(video.raw_media(ele))
        loc = variant(new, video.HLS_MIME)["locations"][0]
        loc["location"] = new_url
        loc["metadata"] = dict(TEST_SIGNED)
        ele.media["fansly"]["media"] = new
        return True

    async def main_download(self, c, ele, username, model_id):
        return "Videos", 10

    monkeypatch.setattr(stream_mod, "refresh_media_link", refresh_media_link)
    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    ele = make_ele(raw)
    # the new playlist is empty here, so the item ends on its direct file
    assert asyncio.run(run_download(session, ele)) == ("Videos", 10)
    assert asked == [ele.id]
    urls = [url for url, _ in session.calls]
    assert urls == ([old_url, new_url] if refreshed else [old_url])
    if refreshed:
        cookies = session.calls[-1][1]["cookies"]
        assert cookies["CloudFront-Signature"] == TEST_SIGNED["Signature"]


# ------------------------------------------------------------------ skipped segments (re-review)

def make_clip_segments(tmp_path, name, rate, vf=None):
    """1-second MPEG-TS segments of a 3-second clip at ``rate``, optionally filtered."""
    seg_dir = tmp_path / name
    seg_dir.mkdir()
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc=size=160x120:rate={rate}:duration=3",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=3"]
    if vf:
        # keep the filter's timestamps: the encoder would round them to the rate
        cmd += ["-vf", vf, "-fps_mode", "passthrough", "-enc_time_base:v", "filter"]
    cmd += ["-c:v", "mpeg4", "-g", "10", "-c:a", "aac", "-shortest",
            "-bsf:v", "dump_extra=freq=keyframe", "-f", "segment", "-segment_time", "1",
            "-segment_format", "mpegts", f"{name}-%d.ts"]
    subprocess.run(cmd, cwd=seg_dir, check=True, capture_output=True)
    return {p.name: p.read_bytes() for p in sorted(seg_dir.glob(f"{name}-*.ts"))}


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("path", ["ffmpeg", "parallel"])
@pytest.mark.parametrize("fault", ["half", "stall", "404"])
def test_a_skipped_segment_fails_the_item(env, tmp_path, monkeypatch, fault, path):
    # the middle of three 1-second segments: stops after half its bytes, stops
    # right after its headers, or is missing. ffmpeg skips it and exits 0;
    # the parallel fetch fails it after its retries and never joins
    monkeypatch.setattr(stream_mod, "get_chunk_timeout", lambda: 2)
    if path == "ffmpeg":
        ffmpeg_only(monkeypatch)
    else:
        fast_retries(monkeypatch)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    assert len(segments) == 3
    raw = raw_media()
    with Server({}, slow_limit=40) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        middle = f"{root}/r2160/segment-1.ts"
        if fault == "404":
            del srv.files[middle]
        else:
            srv.slow[middle] = fault
        ele = make_ele(raw)
        result = download_locally(ele)
    assert result == ("skipped", 0)
    assert list(env.out.iterdir()) == []
    assert len(list(env.temp.iterdir())) == (0 if path == "ffmpeg" else 1)
    assert env.marks == [] and len(env.ffmpeg_runs) == (1 if path == "ffmpeg" else 0)


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize("clip", ["cfr", "ntsc_rounded", "variable_rate", "no_metadata"])
def test_a_clean_copy_passes_the_skipped_segment_check(env, tmp_path, clip):
    # guards against false failures, so it passes with or without the check
    rate, vf = {
        "cfr": ("10", None),
        "ntsc_rounded": ("30000/1001", None),  # 29.97 fps; the metadata says 30 and 3.0 s
        "variable_rate": ("30", "settb=1/600,setpts=(N+0.4*sin(N))/(30*TB)"),  # steps 0.020-0.047 s
        "no_metadata": ("10", None),
    }[clip]
    segments = make_clip_segments(tmp_path, "segment", rate, vf)
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        if clip == "no_metadata":
            set_duration(raw["media"], None)
            assert video.expected_duration(raw["media"]) is None
        ele = make_ele(raw)
        result = download_locally(ele)
    assert result[0] == "Videos" and result[1] > 0
    assert files_in(env.out, env.temp) == [f"{ele.filename}.mp4"]
    assert len(env.marks) == 1


def test_skipped_segment_check_tolerances():
    ten_min = [i / 30 for i in range(30 * 600)]
    assert video.incomplete_reason(ten_min, None, 600.0) is None
    assert video.incomplete_reason(ten_min, None, 602.0) is None  # metadata rounded up
    assert video.incomplete_reason(ten_min, None, None) is None
    # variable frame rate: uneven steps, and a frame held for 0.4 s
    jitter = sorted(i / 30 + 0.4 / 30 * math.sin(i) for i in range(900))
    held = [t if t < 10 else t + 0.4 for t in jitter]
    assert video.incomplete_reason(jitter, None, 30.0) is None
    assert video.incomplete_reason(held, None, 30.4) is None
    # one 6-second segment lost in the middle of ten minutes
    hole = [t for t in ten_min if not 300 <= t < 306]
    assert "missing" in video.incomplete_reason(hole, None, 600.0)
    assert "missing" in video.incomplete_reason(hole, None, None)
    # 0.6 s lost part-way through a segment
    assert "missing" in video.incomplete_reason([t for t in ten_min if not 300 <= t < 300.6])
    # first or last segment lost: only the metadata length can tell
    for cut in (ten_min[180:], ten_min[:-180]):
        assert video.incomplete_reason(cut, None, None) is None
        assert "covers" in video.incomplete_reason(cut, None, 600.0)
    # a hole in separate audio, with whole video
    audio = [i * 1024 / 44100 for i in range(int(600 * 44100 / 1024))]
    assert "audio" in video.incomplete_reason(ten_min, [t for t in audio if not 300 <= t < 306])
    assert video.incomplete_reason([], [], 600.0) == "the copy has no video or audio"
    assert video.expected_duration(raw_media()["media"]) == pytest.approx(26.566667)


# ------------------------------------------------------------------ stream-only videos (#278)

def stream_only(keep_mime):
    """The fixture's accountMedia with no MP4 location and only one stream variant."""
    raw = raw_media()
    other = video.DASH_MIME if keep_mime == video.HLS_MIME else video.HLS_MIME
    drop_variant(raw, other)
    raw["media"]["locations"] = []
    return raw


def read_post(account_media):
    """The Post a timeline read gives for one accountMedia, through normalize."""
    item = {"id": 100000000000000005, "postedAt": "2026-01-02T03:04:05+00:00", "text": "",
            "media": normalize.media_for(account_media)}
    return Post(item, 100000000000000002, "a-creator", responsetype="timeline")


def record_downloads(monkeypatch):
    calls = []

    async def stream_download(self, c, ele, username, model_id):
        calls.append(("stream", ele.id))
        return "Videos", 1

    async def main_download(self, c, ele, username, model_id):
        calls.append(("main", ele.url))
        return "Videos", 1

    monkeypatch.setattr(run_mod.FanslyStreamDownloadManager, "stream_download", stream_download)
    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    return calls


@pytest.mark.parametrize("mime", [video.HLS_MIME, video.DASH_MIME])
def test_viewable_stream_only_video_is_kept_and_takes_the_stream_path(env, monkeypatch, mime):
    raw = stream_only(mime)
    assert raw["access"] is True
    p = read_post(raw)
    assert [m.id for m in p.media] == [int(raw["media"]["id"])]
    assert filters.url_filter(p.media) == p.media
    calls = record_downloads(monkeypatch)
    assert asyncio.run(run_download(None, p.media[0])) == ("Videos", 1)
    assert calls == [("stream", int(raw["media"]["id"]))]


@pytest.mark.parametrize("mime", [video.HLS_MIME, video.DASH_MIME])
def test_unusable_stream_without_an_mp4_is_skipped_not_fetched_as_a_file(env, monkeypatch, mime):
    raw = stream_only(mime)
    ele = read_post(raw).media[0]
    calls = []

    async def main_download(self, c, ele, username, model_id):
        calls.append(ele.url)
        return "Videos", 1

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    # the manifest 404s
    assert asyncio.run(run_download(FakeSession({}), ele)) == ("skipped", 0)
    assert calls == [] and env.ffmpeg_runs == [] and files_in(env.out, env.temp) == []


def test_locked_stream_only_video_stays_locked_and_only_its_preview_is_kept():
    raw = stream_only(video.HLS_MIME)
    raw["access"] = False
    raw["previewId"] = "100000000000000090"
    raw["preview"] = {
        "id": "100000000000000090", "mimetype": "image/jpeg",
        "locations": [{"locationId": "1",
                       "location": "https://cdn3.fansly.com/100000000000000002/100000000000000090.jpeg"}],
    }
    p = read_post(raw)
    full, preview = p.all_media
    assert (full.canview, full.url) == (False, None)
    assert (preview.canview, preview.preview) == (True, 1)
    assert [m.id for m in p.media] == [100000000000000090]


def test_video_with_an_mp4_keeps_the_mp4_as_its_url(env, monkeypatch):
    raw = raw_media()
    direct = raw["media"]["locations"][0]["location"]
    (m,) = normalize.media_for(raw)
    assert m["files"]["full"]["url"] == direct
    p = read_post(raw)
    assert [x.url for x in p.media] == [direct]
    # streams no larger than the MP4: the normal downloader, with the MP4
    for v in raw["media"]["variants"]:
        if v["mimetype"] in (video.HLS_MIME, video.DASH_MIME):
            v["width"], v["height"], v["metadata"] = 1280, 720, "{}"
    calls = record_downloads(monkeypatch)
    assert asyncio.run(run_download(None, read_post(raw).media[0])) == ("Videos", 1)
    assert calls == [("main", direct)]
    assert read_post(raw).media[0].filename == raw["media"]["id"]


def mp4_variants():
    """A video with no locations of its own, its file only on MP4 variants (plus PNG thumbnails)."""
    data = json.loads((FIXTURES / "video_mp4_variants_account_media.json").read_text(encoding="utf-8"))
    return copy.deepcopy(data["response"][0])


def variant_url(raw, variant_id):
    v = next(v for v in raw["media"]["variants"] if v["id"] == variant_id)
    return v["locations"][0]["location"]


def test_largest_mp4_variant_is_the_best_and_images_are_never_picked():
    raw = mp4_variants()
    assert raw["media"]["locations"] == []
    best = video.select_best(raw["media"])
    assert (best.kind, best.width, best.height) == (video.DIRECT, 608, 1080)
    assert best.url == variant_url(raw, "100000000000000033")
    kinds = {c.kind for c in video.candidates(raw["media"])}
    assert kinds == {video.DIRECT}
    assert not any(c.url.endswith(".png") for c in video.candidates(raw["media"]))
    assert video.has_direct(raw["media"])


def test_video_with_only_mp4_variants_is_kept_and_uses_the_normal_downloader(env, monkeypatch):
    raw = mp4_variants()
    p = read_post(raw)
    assert [m.id for m in p.media] == [100000000000000031]
    ele = p.media[0]
    assert ele.url == variant_url(raw, "100000000000000033")
    assert video.uses_stream(ele) is False
    calls = record_downloads(monkeypatch)
    assert asyncio.run(run_download(None, ele)) == ("Videos", 1)
    assert calls == [("main", variant_url(raw, "100000000000000033"))]


@pytest.mark.parametrize("case", ["mp4_variant", "hls_only", "dash_only"])
def test_variant_files_are_named_by_media_id(env, case):
    raw = {"mp4_variant": mp4_variants, "hls_only": lambda: stream_only(video.HLS_MIME),
           "dash_only": lambda: stream_only(video.DASH_MIME)}[case]()
    ele = read_post(raw).media[0]
    assert ele.url and raw["media"]["id"] not in ele.url
    assert ele.filename == raw["media"]["id"]
    assert ele.no_quality_final_filename == raw["media"]["id"]
    assert ele.mpd is None and ele.protected is False


@pytest.mark.parametrize("mime,ext", [("image/gif", "gif"), ("image/jpeg", "jpeg")])
def test_non_video_with_an_mp4_variant_keeps_its_own_file(mime, ext):
    own = f"https://cdn3.fansly.com/100000000000000002/100000000000000040.{ext}"
    account_media = {
        "id": "100000000000000041", "access": True, "previewId": None,
        "media": {
            "id": "100000000000000040", "mimetype": mime, "width": 480, "height": 480,
            "locations": [{"locationId": "1", "location": own}],
            "variants": [{
                "id": "100000000000000042", "mimetype": "video/mp4", "width": 960, "height": 960,
                "locations": [{"locationId": "1", "location":
                               "https://cdn3.fansly.com/100000000000000002/100000000000000042.mp4"}],
            }],
        },
    }
    (m,) = normalize.media_for(account_media)
    assert (m["type"], m["files"]["full"]["url"]) == ("photo", own)


class MetadataSession:
    def __init__(self):
        self.urls = []

    def requests_async(self, url=None, **kw):
        self.urls.append(url)
        raise AssertionError("metadata mode fetched the stream URL")


@pytest.mark.parametrize("case", ["hls_only", "dash_only", "mp4_and_4k_hls"])
def test_metadata_mode_does_not_fetch_a_stream_and_uses_mp4(env, monkeypatch, case):
    monkeypatch.setattr(meta_mod.cache, "get", lambda *a, **k: None)
    raw = {"hls_only": lambda: stream_only(video.HLS_MIME),
           "dash_only": lambda: stream_only(video.DASH_MIME), "mp4_and_4k_hls": raw_media}[case]()
    ele = read_post(raw).media[0]
    assert video.uses_stream(ele)
    session = MetadataSession()
    ph = asyncio.run(meta_mod.MetaDataManager()._placeholderObjHelper(session, ele))
    assert session.urls == [] and ph._ext == "mp4"


def test_db_protected_does_not_count_fansly_dash_links(env):
    dash = {"link": "https://cdn3.fansly.com/new/1/2/2.mpd"}
    assert db_command.is_protected(dash) is False
    env.stub.site = "onlyfans"
    assert db_command.is_protected({"link": "https://cdn3.onlyfans.com/dash/files/a/b.mpd"}) is True
    assert db_command.is_protected({"link": "https://cdn2.onlyfans.com/files/a/b.mp4"}) is False


def test_unusable_stream_falls_back_to_an_mp4_variant(env, monkeypatch):
    # a 4K HLS stream that 404s, next to a 1080 MP4 variant and no file of its own
    raw = mp4_variants()
    hls = copy.deepcopy(variant(raw_media()["media"], video.HLS_MIME))
    raw["media"]["variants"].append(hls)
    ele = read_post(raw).media[0]
    assert video.uses_stream(ele) is True
    calls = []

    async def main_download(self, c, ele, username, model_id):
        calls.append(ele.url)
        return "Videos", 10

    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", main_download)
    assert asyncio.run(run_download(FakeSession({}), ele)) == ("Videos", 10)
    assert calls == [variant_url(raw, "100000000000000033")]


# ------------------------------------------------------------------ parallel segments (#292)

def make_many_segments(tmp_path, name, seconds=6, step=0.5):
    """MPEG-TS segments of ``step`` seconds (keyframe every step) of a ``seconds`` clip."""
    seg_dir = tmp_path / name
    seg_dir.mkdir()
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=10:duration={seconds}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
           "-c:v", "mpeg4", "-g", str(int(step * 10)), "-c:a", "aac", "-shortest",
           "-bsf:v", "dump_extra=freq=keyframe", "-f", "segment", "-segment_time", str(step),
           "-segment_format", "mpegts", f"{name}-%02d.ts"]
    subprocess.run(cmd, cwd=seg_dir, check=True, capture_output=True)
    return {p.name: p.read_bytes() for p in sorted(seg_dir.glob(f"{name}-*.ts"))}


def probe_streams(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type,codec_name,duration,nb_frames",
         "-of", "json", str(path)], check=True, capture_output=True, text=True).stdout
    return sorted(json.loads(out)["streams"], key=lambda s: s["codec_type"])


@pytest.mark.slow
@needs_ffmpeg
def test_segments_are_fetched_in_parallel_within_the_limit_and_match_ffmpeg(env, tmp_path, monkeypatch):
    segments = make_many_segments(tmp_path, "segment")
    assert len(segments) == 12
    raw = raw_media()
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 3)
    with Server({}) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        set_duration(raw["media"], 6.0)
        for name in segments:
            srv.delay[f"{root}/r2160/{name}"] = 0.3
        ele = make_ele(raw)
        assert download_locally(ele)[0] == "Videos"
        assert srv.peak == 3  # several at once, never more than the limit
        parallel = tmp_path / "parallel.mp4"
        (env.out / f"{ele.filename}.mp4").rename(parallel)
        assert len(env.ffmpeg_runs) == 1  # the join

        ffmpeg_only(monkeypatch)
        srv.peak = 0
        assert download_locally(make_ele(raw))[0] == "Videos"
        assert srv.peak == 1  # ffmpeg alone: one request at a time
        single = env.out / f"{ele.filename}.mp4"

    assert all(f"{root}/r2160/{n}" in [p for p, _ in srv.seen] for n in segments)
    a, b = probe_streams(parallel), probe_streams(single)
    assert [(s["codec_type"], s["codec_name"], s.get("nb_frames")) for s in a] == \
        [(s["codec_type"], s["codec_name"], s.get("nb_frames")) for s in b]
    for x, y in zip(a, b):
        assert abs(float(x["duration"]) - float(y["duration"])) < 0.1  # within a frame at 10 fps
    assert list(env.temp.iterdir()) == []


@needs_ffmpeg
def test_a_segment_that_fails_once_is_retried_and_the_file_downloads(env, tmp_path, monkeypatch):
    fast_retries(monkeypatch, attempts=3)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        middle = f"{root}/r2160/segment-1.ts"
        srv.fail[middle] = 1
        ele = make_ele(raw)
        result = download_locally(ele)
    assert result[0] == "Videos" and result[1] > 0
    assert [p for p, _ in srv.seen].count(middle) == 2
    assert files_in(env.out, env.temp) == [f"{ele.filename}.mp4"]
    assert list(env.temp.iterdir()) == [] and len(env.marks) == 1


@needs_ffmpeg
def test_a_segment_that_fails_every_retry_fails_the_file_and_keeps_the_segments(env, tmp_path, monkeypatch):
    fast_retries(monkeypatch, attempts=3)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        middle = f"{root}/r2160/segment-1.ts"
        srv.fail[middle] = 99
        result = download_locally(make_ele(raw))
    assert result == ("skipped", 0)
    assert [p for p, _ in srv.seen].count(middle) == 3
    assert list(env.out.iterdir()) == [] and len(list(env.temp.iterdir())) == 1
    assert env.marks == [] and env.ffmpeg_runs == []


@needs_ffmpeg
def test_cancelled_parallel_download_keeps_the_segments(env, tmp_path):
    segments = make_many_segments(tmp_path, "segment")
    raw = raw_media()
    with Server({}, slow_limit=40) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        srv.slow[f"{root}/r2160/segment-05.ts"] = "trickle"
        ele = make_ele(raw)

        async def go():
            async with ofsession.download_session() as c:
                task = asyncio.ensure_future(run_download(c, ele))
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline and not any(
                        p.is_file() for p in env.temp.rglob("*.ts")):
                    await asyncio.sleep(0.05)
                assert any(env.temp.rglob("*.ts")), "no segment was written"
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

        asyncio.run(go())
    assert list(env.out.iterdir()) == [] and len(list(env.temp.iterdir())) == 1
    assert env.marks == [] and env.ffmpeg_runs == []


@pytest.mark.slow
@needs_ffmpeg
def test_a_trickling_segment_hits_the_overall_time_limit(env, tmp_path, monkeypatch):
    monkeypatch.setattr(stream_mod, "STREAM_TIMEOUT_FLOOR", 4)
    monkeypatch.setattr(stream_mod, "get_chunk_timeout", lambda: 30)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}, slow_limit=40) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        srv.slow[f"{root}/r2160/segment-1.ts"] = "trickle"
        started = time.monotonic()
        result = download_locally(make_ele(raw))
        elapsed = time.monotonic() - started
    assert elapsed < 20 and result == ("skipped", 0)
    assert list(env.out.iterdir()) == [] and len(list(env.temp.iterdir())) == 1


@needs_ffmpeg
def test_fmp4_init_segment_and_order_are_kept(env, tmp_path, monkeypatch):
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 4)
    hls_dir = tmp_path / "fmp4"
    hls_dir.mkdir()
    ffmpeg_make(["-f", "hls", "-hls_time", "1", "-hls_segment_type", "fmp4",
                 "-hls_playlist_type", "vod", "-hls_segment_filename", "part%d.m4s",
                 "media.m3u8"], hls_dir)
    playlist = (hls_dir / "media.m3u8").read_text(encoding="utf-8")
    assert "#EXT-X-MAP" in playlist
    raw = raw_media()
    with Server({}) as srv:
        url = point_at(raw["media"], video.HLS_MIME, srv.base)
        root = urlparse(url).path.rsplit("/", 1)[0]
        srv.files[urlparse(url).path] = VIDEO_ONLY_MASTER.encode()
        srv.files.update({f"{root}/r2160/{p.name}": p.read_bytes() for p in hls_dir.iterdir()})
        # the first segments arrive last
        names = sorted(p.name for p in hls_dir.glob("part*.m4s"))
        for i, name in enumerate(names):
            srv.delay[f"{root}/r2160/{name}"] = 0.2 * (len(names) - i)
        ele = make_ele(raw)
        result = download_locally(ele)
    assert result[0] == "Videos"
    out = env.out / f"{ele.filename}.mp4"
    info = probe(out)
    assert sorted(s["codec_type"] for s in info["streams"]) == ["audio", "video"]
    assert 2.0 < float(info["format"]["duration"]) < 4.0
    assert f"{root}/r2160/init.mp4" in [p for p, _ in srv.seen]
    times = stream_mod._packet_times(FFPROBE, out, "v:0")
    assert times == sorted(times) and video.incomplete_reason(times, None, 3.0) is None
    assert list(env.temp.iterdir()) == []


def test_local_playlist_keeps_the_init_segment_and_the_order():
    text = ("#EXTM3U\n#EXT-X-VERSION:7\n#EXT-X-TARGETDURATION:2\n#EXT-X-KEY:METHOD=NONE\n"
            '#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2.0,\nseg-b.m4s?x=1\n#EXTINF:2.0,\nseg-a.m4s\n'
            "#EXTINF:1.5,\nhttps://other.cdn/seg-c\n#EXT-X-ENDLIST\n")
    plan = video.local_playlist(text, "https://cdn.example/v/media.m3u8", "v")
    assert plan.files == [
        ("https://cdn.example/v/init.mp4", "vinit00000.mp4"),
        ("https://cdn.example/v/seg-b.m4s?x=1", "v00000.m4s"),
        ("https://cdn.example/v/seg-a.m4s", "v00001.m4s"),
        ("https://other.cdn/seg-c", "v00002.m4s"),
    ]
    assert plan.text.splitlines() == [
        "#EXTM3U", "#EXT-X-VERSION:7", "#EXT-X-TARGETDURATION:2", "#EXT-X-KEY:METHOD=NONE",
        '#EXT-X-MAP:URI="vinit00000.mp4"', "#EXTINF:2.0,", "v00000.m4s", "#EXTINF:2.0,",
        "v00001.m4s", "#EXTINF:1.5,", "v00002.m4s", "#EXT-X-ENDLIST"]


UNEXPECTED = {
    "sample_aes": "#EXT-X-KEY:METHOD=SAMPLE-AES,URI=\"k.key\"\n",
    "nested": '#EXT-X-STREAM-INF:BANDWIDTH=1\n',
    "partial": '#EXT-X-PART:DURATION=1,URI="p.m4s"\n',
    "preload": '#EXT-X-PRELOAD-HINT:TYPE=PART,URI="p.m4s"\n',
    "skip": '#EXT-X-SKIP:SKIPPED-SEGMENTS=2\n',
    "session_key": '#EXT-X-SESSION-KEY:METHOD=AES-128,URI="key.bin"\n',
}


@pytest.mark.parametrize("case", [*UNEXPECTED, "no_endlist", "not_m3u8", "no_segments", "file_url"])
def test_unexpected_playlist_is_refused_by_the_planner(case):
    head = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n"
    body = UNEXPECTED.get(case, "") + "#EXTINF:6.0,\nsegment-0.ts\n"
    text = {"no_endlist": head + body,
            "not_m3u8": "<html></html>\n",
            "no_segments": head + "#EXT-X-ENDLIST\n",
            "file_url": head + "#EXTINF:6.0,\nfile:///etc/passwd\n#EXT-X-ENDLIST\n",
            }.get(case, head + body + "#EXT-X-ENDLIST\n")
    with pytest.raises(video.UnexpectedPlaylist):
        video.local_playlist(text, "https://cdn.example/v/media.m3u8", "v")


@pytest.mark.parametrize("case", ["sample_aes", "partial", "preload", "skip", "session_key", "nested", "no_endlist"])
def test_unexpected_playlist_falls_back_to_ffmpeg(env, monkeypatch, case):
    raw = raw_media()
    hls_url = variant(raw["media"], video.HLS_MIME)["locations"][0]["location"]
    rendition = video.best_rendition(MASTER, hls_url)[0]
    playlist = (FIXTURES / "media_playlist.m3u8").read_text(encoding="utf-8")
    if case == "no_endlist":
        playlist = playlist.replace("#EXT-X-ENDLIST", "")
    else:
        playlist = playlist.replace("#EXTINF", UNEXPECTED[case] + "#EXTINF", 1)
    session = FakeSession({hls_url: MASTER, rendition: playlist})
    ffmpeg_urls = []

    async def fake_ffmpeg(self, url, temp, cookies, audio_url=None, timeout=None):
        ffmpeg_urls.append(url)
        temp.write_bytes(b"\0" * 2048)

    async def ok(*a, **k):
        return None

    async def no_segments(*a, **k):
        raise AssertionError("segments fetched in parallel")

    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_run_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_fetch_segments", no_segments)
    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_integrity_check", ok)
    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_check_complete", ok)
    assert asyncio.run(run_download(session, make_ele(raw, direct=False))) == ("Videos", 2048)
    assert ffmpeg_urls == [rendition]


def test_segment_limit_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("OFSC_FANSLY_STREAM_SEGMENTS", "3")
    import ofscraper.utils.of_env.values.main as main_values

    assert main_values.load_main_config()["FANSLY_STREAM_SEGMENTS"] == 3
    real = stream_mod.of_env.getattr
    for value, expected in ((8, 8), (0, 0), (-2, 0), ("x", 0)):
        monkeypatch.setattr(stream_mod.of_env, "getattr",
                            lambda key, *a, _v=value, **k: _v if key == "FANSLY_STREAM_SEGMENTS" else real(key, *a, **k))
        assert stream_mod.segment_limit() == expected


# ------------------------------------------------------------------ review fixes (#295)

@needs_ffmpeg
def test_join_works_when_the_folder_name_has_a_hash(env, tmp_path, monkeypatch):
    # ffmpeg's HLS reader resolves segment names against the playlist path as
    # a URL, so a "#" in that path used to cut it short and fail every join
    hashed = env.temp / "new video #tag"
    hashed.mkdir()

    class HashTemp:
        def __init__(self, ele, name):
            self.tempfilepath = hashed / f"x #1_{name}"

        async def init(self):
            return self

    monkeypatch.setattr(stream_mod.placeholder, "tempFilePlaceholder", HashTemp)
    video_segments = make_segments(tmp_path, "v", "-an", "-bsf:v", "dump_extra=freq=keyframe")
    audio_segments = make_segments(tmp_path, "a", "-vn")
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, SPLIT_AUDIO_MASTER, {"r2160": video_segments, "audio": audio_segments})
        ele = make_ele(raw)
        result = download_locally(ele)
    assert result[0] == "Videos" and result[1] > 0
    out = env.out / f"{ele.filename}.mp4"
    assert sorted(s["codec_type"] for s in probe(out)["streams"]) == ["audio", "video"]
    (join,) = env.ffmpeg_runs
    assert "#" in str(env.ffmpeg_cwds[0]) and env.ffmpeg_cwds[0].name.endswith(".segments")
    assert env.ffmpeg_cwds[0].name.startswith(".")
    assert join[join.index("-i") + 1] == "video.m3u8"
    assert [a for a in join if str(a).endswith(".m3u8")] == ["video.m3u8", "audio.m3u8"]
    assert list(hashed.iterdir()) == []


@pytest.mark.slow
@needs_ffmpeg
def test_the_join_gets_only_the_time_left(env, tmp_path, monkeypatch):
    monkeypatch.setattr(stream_mod, "STREAM_TIMEOUT_FLOOR", 30)
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    raw = raw_media()
    with Server({}) as srv:
        root = serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        for name in segments:
            srv.delay[f"{root}/r2160/{name}"] = 1.0
        assert download_locally(make_ele(raw))[0] == "Videos"
    (timeout,) = env.ffmpeg_timeouts
    assert timeout <= 30 - 0.9  # the fetch took at least a second of the 30


@needs_ffmpeg
def test_not_enough_space_for_the_join_fails_clearly(env, tmp_path, monkeypatch, caplog):
    segments = make_segments(tmp_path, "segment", "-bsf:v", "dump_extra=freq=keyframe")
    size = sum(len(b) for b in segments.values())
    free = []

    def small_drive(path):
        free.append(path)
        return size + 1000  # the segments fit, the margin doesn't

    monkeypatch.setattr(stream_mod, "_free_space", small_drive)
    # a logger that reaches caplog ("shared" doesn't propagate)
    monkeypatch.setattr(common_globals, "log", logging.getLogger("test_fansly_join_space"))
    raw = raw_media()
    with Server({}) as srv:
        serve_hls(srv, raw, VIDEO_ONLY_MASTER, {"r2160": segments})
        with caplog.at_level("DEBUG", logger="test_fansly_join_space"):
            result = download_locally(make_ele(raw))
    assert result == ("skipped", 0)
    assert "not enough disk space to join the stream" in caplog.text
    assert free == [env.temp]  # the drive of the .part
    assert env.ffmpeg_runs == [] and env.marks == []
    assert list(env.out.iterdir()) == [] and len(list(env.temp.iterdir())) == 1


def test_file_writes_run_off_the_event_loop_and_a_cancel_waits_for_them():
    calls = []

    def slow_write(data):
        time.sleep(0.3)
        calls.append((data, threading.get_ident()))

    async def go():
        main = threading.get_ident()
        await stream_mod._off_loop(slow_write, b"a")
        task = asyncio.ensure_future(stream_mod._off_loop(slow_write, b"b"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # the cancelled write had finished before the cancel went on
        assert [d for d, _ in calls] == [b"a", b"b"]
        assert all(t != main for _, t in calls)

    asyncio.run(go())

# ------------------------------------------------------------------ segment resume (#443)

@pytest.fixture
def resume_env(env, monkeypatch):
    fast_retries(monkeypatch, attempts=1)
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 1)
    env.tempfile = env.temp / "video.part"
    env.folder = stream_mod.segment_folder(env.tempfile)
    env.playlists = (video.local_playlist(
        "#EXTM3U\n#EXTINF:1,\n0.ts?sig=old\n#EXTINF:1,\n1.ts?sig=old\n"
        "#EXTINF:1,\n2.ts?sig=old\n#EXT-X-ENDLIST\n", "https://cdn.example/variant/", "v"
    ), None)
    env.calls = []
    env.fault = None
    env.manager = stream_mod.FanslyStreamDownloadManager()

    class Response:
        ok, status = True, 200
        headers = {"content-length": "2"}

        async def iter_chunked(self, size):
            yield b"a"
            if env.fault:
                fault = env.fault
                env.fault = None
                raise fault
            yield b"b"

    @contextlib.asynccontextmanager
    async def request(url=None, **kwargs):
        env.calls.append(url)
        # Complete the first segment before interrupting the second.
        if urlparse(url).path.endswith("1.ts") and env.failure:
            env.fault = env.failure
        yield Response()

    env.failure = None
    env.session = SimpleNamespace(requests_async=request)

    async def join(cmd, temp, timeout, what, cwd=None):
        assert cwd == env.folder
        names = [line for line in (cwd / "video.m3u8").read_text().splitlines()
                 if not line.startswith("#")]
        temp.write_bytes(b"".join((cwd / name).read_bytes() for name in names))

    monkeypatch.setattr(env.manager, "_run_cmd", join)
    return env


def parallel_run(env, playlists=None):
    return asyncio.run(env.manager._parallel_copy(
        env.session, playlists or env.playlists, env.tempfile, {}, 30
    ))


def test_resume_fetches_only_missing_segments_after_a_failure(resume_env):
    e = resume_env
    e.failure = OSError("interrupted")
    with pytest.raises(stream_mod.SegmentError):
        parallel_run(e)
    assert e.folder.is_dir()
    assert (e.folder / "v00000.ts").read_bytes() == b"ab"
    assert not (e.folder / "v00001.ts").exists()
    assert (e.folder / "v00001.ts.tmp").read_bytes() == b"a"
    assert e.folder.name.startswith(".")
    if stream_mod.os.name == "nt":
        assert stream_mod.ctypes.windll.kernel32.GetFileAttributesW(str(e.folder)) & 2
    saved = (e.folder / "manifest.json").read_text()
    assert "sig=" not in saved
    e.failure = None
    # Signatures may change between runs; abandoned temporary files go away.
    (e.folder / "abandoned.tmp").write_bytes(b"partial")
    original_join = e.manager._run_cmd

    async def join(*args, **kwargs):
        assert not (e.folder / "abandoned.tmp").exists()
        await original_join(*args, **kwargs)

    e.manager._run_cmd = join
    playlist = e.playlists[0]
    refreshed = video.LocalPlaylist(playlist.text, [
        (url.replace("sig=old", "sig=new"), name) for url, name in playlist.files
    ])
    before = len(e.calls)
    parallel_run(e, (refreshed, None))
    assert e.calls[before:] == [url for url, _ in refreshed.files[1:]]
    resumed = e.tempfile.read_bytes()
    assert not e.folder.exists()
    e.calls.clear()
    parallel_run(e)
    assert len(e.calls) == 3 and e.tempfile.read_bytes() == resumed == b"ababab"


@pytest.mark.parametrize("resume", [True, False])
def test_cancel_keeps_only_completed_segments_when_resuming(resume_env, resume):
    e = resume_env
    e.stub.auto_resume = resume
    e.failure = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        parallel_run(e)
    assert e.folder.exists() == resume
    if resume:
        assert (e.folder / "v00000.ts").read_bytes() == b"ab"
        assert not (e.folder / "v00001.ts").exists()


@pytest.mark.parametrize("change", ["variant", "segments", "invalid", "disabled"])
def test_incompatible_or_disabled_resume_refetches_everything(resume_env, change):
    e = resume_env
    e.failure = OSError("interrupted")
    with pytest.raises(stream_mod.SegmentError):
        parallel_run(e)
    e.failure = None
    playlist = e.playlists[0]
    if change == "variant":
        playlist = video.LocalPlaylist(playlist.text, [
            (url.replace("/variant/", "/other/"), name) for url, name in playlist.files
        ])
    elif change == "segments":
        playlist = video.LocalPlaylist(playlist.text, [
            (url.replace("0.ts", "different.ts"), name) for url, name in playlist.files
        ])
    elif change == "invalid":
        (e.folder / "manifest.json").write_text("broken")
    else:
        e.stub.auto_resume = False
    e.calls.clear()
    parallel_run(e, (playlist, None))
    assert e.calls == [url for url, _ in playlist.files]
    assert not e.folder.exists()


def test_failed_download_without_resume_removes_segments(resume_env):
    e = resume_env
    e.stub.auto_resume = False
    e.failure = OSError("interrupted")
    with pytest.raises(stream_mod.SegmentError):
        parallel_run(e)
    assert not e.folder.exists()


def test_failure_to_hide_segments_is_only_logged(resume_env, monkeypatch, caplog):
    e = resume_env
    def fail(*args):
        raise OSError("hidden attribute unavailable")
    monkeypatch.setattr(stream_mod.ctypes, "windll", SimpleNamespace(kernel32=SimpleNamespace(
        GetFileAttributesW=lambda path: 16, SetFileAttributesW=fail)), raising=False)
    monkeypatch.setattr(common_globals, "log", logging.getLogger("test_hide_segments"))
    # Call the Windows branch even on non-Windows test hosts.
    with monkeypatch.context() as patch:
        patch.setattr(stream_mod.os, "name", "nt")
        with caplog.at_level("DEBUG", logger="test_hide_segments"):
            stream_mod._hide_folder(e.folder)
    assert "Could not hide stream segments folder" in caplog.text
    parallel_run(e)
    assert e.tempfile.read_bytes() == b"ababab"

@pytest.mark.parametrize("skip", ["size", "script"])
def test_skip_after_join_removes_segments(resume_env, monkeypatch, skip):
    e = resume_env
    ele = make_ele(raw_media())
    temp = e.temp / f"{ele.filename or ele.id}_{ele.id}_{ele.post_id}.part"
    e.tempfile, e.folder = temp, stream_mod.segment_folder(temp)

    async def urls(*args):
        return "https://cdn.example/media.m3u8", None

    async def playlists(*args):
        return e.playlists

    async def noop(*args):
        pass

    async def skip_script(*args):
        return True

    monkeypatch.setattr(e.manager, "_stream_urls", urls)
    monkeypatch.setattr(e.manager, "_local_playlists", playlists)
    monkeypatch.setattr(e.manager, "_check_complete", noop)
    monkeypatch.setattr(e.manager, "_force_download", noop)
    if skip == "size":
        e.stub.size_max = 1
    else:
        monkeypatch.setattr(dm, "skip_download_script", skip_script)
    asyncio.run(e.manager._stream_download(e.session, ele, "a-creator", ele.model_id))
    assert len(e.calls) == 3
    assert not e.folder.exists() and not temp.exists()
    assert list(e.out.iterdir()) == []


@pytest.mark.parametrize("mode", ["direct", "protected", "ffmpeg"])
def test_fallback_or_protected_skip_cleans_old_segments(env, monkeypatch, mode):
    manager = stream_mod.FanslyStreamDownloadManager()
    ele = make_ele(raw_media(), direct=mode != "protected")
    temp = env.temp / f"{ele.filename or ele.id}_{ele.id}_{ele.post_id}.part"
    folder = stream_mod.segment_folder(temp)
    folder.mkdir()
    (folder / "old.ts").write_bytes(b"old")

    async def urls(*args):
        if mode == "protected":
            raise video.ProtectedStream("protected")
        if mode == "direct":
            raise video.StreamError("use direct")
        return "https://cdn.example/media.m3u8", None

    async def ffmpeg(*args):
        assert not folder.exists()
        temp.write_bytes(b"joined")

    async def noop(*args):
        pass

    async def finish(*args):
        temp.unlink()
        return "Videos", 6

    monkeypatch.setattr(manager, "_stream_urls", urls)
    monkeypatch.setattr(manager, "_run_ffmpeg", ffmpeg)
    monkeypatch.setattr(manager, "_check_complete", noop)
    monkeypatch.setattr(manager, "_integrity_check", noop)
    monkeypatch.setattr(manager, "_finish", finish)
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 0)
    asyncio.run(manager._stream_download(None, ele, "a-creator", ele.model_id))
    assert not folder.exists()


@pytest.mark.parametrize("resume", [True, False])
def test_temp_cleanup_handles_hidden_segment_folders(env, monkeypatch, resume):
    import ofscraper.utils.paths.paths as paths
    from ofscraper.commands.scraper.actions.download import stop

    env.stub.auto_resume = resume
    folder = stream_mod.segment_folder(env.temp / "video.part")
    folder.mkdir()
    (folder / "v00000.ts").write_bytes(b"segment")
    part = env.temp / "video.part"
    part.write_bytes(b"incomplete join")
    monkeypatch.setattr(paths.data, "get_TempDir", lambda: env.temp)
    real_getattr = paths.of_env.getattr
    monkeypatch.setattr(paths.of_env, "getattr", lambda key, *a, **kw:
                        True if key == "BATCH_TEMPFILE_CLEANUP" else real_getattr(key, *a, **kw))
    monkeypatch.setattr(stop, "requested", threading.Event())
    paths.temp_cleanup()
    assert folder.exists() == resume and part.exists() == resume


def test_failed_join_keeps_segments_but_removes_partial_output(resume_env, monkeypatch):
    e = resume_env
    ele = make_ele(raw_media())
    e.tempfile = e.temp / f"{ele.filename or ele.id}_{ele.id}_{ele.post_id}.part"
    e.folder = stream_mod.segment_folder(e.tempfile)

    async def urls(*args):
        return "https://cdn.example/media.m3u8", None

    async def playlists(*args):
        return e.playlists

    async def fail_join(*args, **kwargs):
        e.tempfile.write_bytes(b"partial join")
        raise OSError("join failed")

    monkeypatch.setattr(e.manager, "_stream_urls", urls)
    monkeypatch.setattr(e.manager, "_local_playlists", playlists)
    monkeypatch.setattr(e.manager, "_run_cmd", fail_join)
    with pytest.raises(OSError, match="join failed"):
        asyncio.run(e.manager._stream_download(e.session, ele, "a-creator", ele.model_id))
    assert not e.tempfile.exists()
    assert [(e.folder / name).read_bytes() for _, name in e.playlists[0].files] == [b"ab"] * 3
# ------------------------------------------------------------------ more resumable streams (#444)


def dash_mpd(body, **attrs):
    attributes = {"xmlns": "urn:mpeg:dash:schema:mpd:2011", "type": "static",
                  "mediaPresentationDuration": "PT3S", **attrs}
    return '<MPD ' + ' '.join(f'{k}="{v}"' for k, v in attributes.items()) + '>' + body + '</MPD>'


def dash_rep(address, base='', rep_id='high', bandwidth=900):
    return (f'<Representation id="{rep_id}" bandwidth="{bandwidth}">'
            + (f'<BaseURL>{base}</BaseURL>' if base else '') + address + '</Representation>')


@pytest.mark.parametrize('address, expected', [
    ('<SegmentTemplate initialization="init-$RepresentationID$.mp4" media="s-$Number%03d$.m4s" '
     'duration="10" timescale="10" startNumber="7"/>',
     ['init-high.mp4', 's-007.m4s', 's-008.m4s', 's-009.m4s']),
    ('<SegmentTemplate media="s-$Time$.m4s" timescale="10" duration="10" startNumber="7"/>',
     ['s-0.m4s', 's-10.m4s', 's-20.m4s']),
    ('<SegmentTemplate initialization="init.mp4" media="s-$Time$.m4s" timescale="10">'
     '<SegmentTimeline><S t="20" d="10" r="2"/></SegmentTimeline></SegmentTemplate>',
     ['init.mp4', 's-20.m4s', 's-30.m4s', 's-40.m4s']),
    ('<SegmentTemplate media="s-$Time$.m4s" timescale="10">'
     '<SegmentTimeline><S d="10" r="-1"/></SegmentTimeline></SegmentTemplate>',
     ['s-0.m4s', 's-10.m4s', 's-20.m4s']),
    ('<SegmentTemplate media="s-$Number$.m4s" startNumber="4">'
     '<SegmentTimeline><S d="1" r="-1"/><S t="2" d="1"/></SegmentTimeline></SegmentTemplate>',
     ['s-4.m4s', 's-5.m4s', 's-6.m4s']),
    ('<SegmentList><Initialization sourceURL="init.mp4"/><SegmentURL media="b.m4s"/>'
     '<SegmentURL media="a.m4s"/></SegmentList>', ['init.mp4', 'b.m4s', 'a.m4s']),
    ('<SegmentBase indexRange="100-200"><Initialization range="0-99"/></SegmentBase>', ['']),
    ('', ['']),
])
def test_dash_planner_resolves_every_base_and_keeps_file_order(address, expected):
    base = 'track.mp4' if expected == [''] else 'rep/'
    mpd = dash_mpd('<BaseURL>../root/</BaseURL><Period><BaseURL>period/</BaseURL>'
                   '<AdaptationSet mimeType="video/mp4"><BaseURL>adapt/</BaseURL>'
                   + dash_rep(address, base) + '</AdaptationSet></Period>')
    track, audio = video.local_dash(mpd, 'https://cdn.example/manifests/movie.mpd')
    root = 'https://cdn.example/root/period/adapt/' + base
    assert [url for url, _ in track.files] == [root + name for name in expected]
    assert track.pieces == [name for _, name in track.files]
    assert audio is None


def test_dash_chooses_highest_bandwidth_video_and_audio_and_inherits_template():
    template = '<SegmentTemplate initialization="$RepresentationID$-init.mp4" media="$RepresentationID$-$Number$.m4s" duration="1"/>'
    mpd = dash_mpd('<Period><AdaptationSet mimeType="video/mp4">' + template
                   + dash_rep('', rep_id='vlo', bandwidth=100)
                   + dash_rep('<SegmentTemplate startNumber="8"/>', rep_id='vhi')
                   + '</AdaptationSet><AdaptationSet mimeType="audio/mp4">' + template
                   + dash_rep('', rep_id='ahi', bandwidth=200)
                   + dash_rep('', rep_id='alo', bandwidth=50)
                   + '</AdaptationSet></Period>')
    v, a = video.local_dash(mpd, 'https://cdn.example/m.mpd')
    assert [url.rsplit('/', 1)[-1] for url, _ in v.files] == ['vhi-init.mp4', 'vhi-8.m4s', 'vhi-9.m4s', 'vhi-10.m4s']
    assert [url.rsplit('/', 1)[-1] for url, _ in a.files] == ['ahi-init.mp4', 'ahi-1.m4s', 'ahi-2.m4s', 'ahi-3.m4s']
    assert 'vhi' in v.text and 'ahi' in a.text


def test_dash_chooses_tracks_as_ffmpeg_does():
    # ffmpeg (the network path) takes the largest video and the audio with
    # the most channels, whatever their bandwidth; bandwidth breaks ties
    template = '<SegmentTemplate media="$RepresentationID$-$Number$.m4s" duration="1"/>'
    stereo = '<AudioChannelConfiguration schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011" value="2"/>'
    surround = stereo.replace('value="2"', 'value="6"')
    mpd = dash_mpd('<Period><AdaptationSet mimeType="video/mp4">' + template
                   + '<Representation id="v4k" bandwidth="100" width="3840" height="2160"/>'
                   + '<Representation id="v720" bandwidth="900" width="1280" height="720"/>'
                   + '<Representation id="v4k2" bandwidth="200" width="3840" height="2160"/>'
                   + '</AdaptationSet><AdaptationSet mimeType="audio/mp4">' + template
                   + f'<Representation id="a2" bandwidth="900">{stereo}</Representation>'
                   + f'<Representation id="a6" bandwidth="100">{surround}</Representation>'
                   + '</AdaptationSet></Period>')
    v, a = video.local_dash(mpd, 'https://cdn.example/m.mpd')
    assert v.files[0][0].endswith('/v4k2-1.m4s')
    assert a.files[0][0].endswith('/a6-1.m4s')


@pytest.mark.parametrize('body, attrs, reason', [
    ('<Period/>', {'type': 'dynamic'}, 'dynamic'),
    ('<Period/><Period/>', {}, 'exactly one'),
    ('<Period><ContentProtection/></Period>', {}, 'protected'),
    ('<Period><AdaptationSet mimeType="video/webm">' + dash_rep('', 'v.webm') + '</AdaptationSet></Period>', {}, 'MP4'),
    ('<Period><AdaptationSet mimeType="video/mp4">' + dash_rep('<SegmentTemplate media="$Number$.m4s"/>') + '</AdaptationSet></Period>', {}, 'duration'),
])
def test_unusual_dash_is_refused(body, attrs, reason):
    with pytest.raises(video.UnexpectedPlaylist, match=reason):
        video.local_dash(dash_mpd(body, **attrs), 'https://cdn.example/m.mpd')


@pytest.mark.parametrize('body, attrs', [('<Period/>', {'type': 'dynamic'}), ('<Period/><Period/>', {})])
def test_unusual_dash_falls_back_to_ffmpeg(env, monkeypatch, body, attrs, caplog):
    manager = stream_mod.FanslyStreamDownloadManager()
    url = 'https://cdn.example/m.mpd'
    calls = []
    async def ffmpeg(*args):
        calls.append(args)
    monkeypatch.setattr(manager, '_run_ffmpeg', ffmpeg)
    with caplog.at_level('INFO', logger='shared'):
        asyncio.run(manager._copy_stream(FakeSession({url: dash_mpd(body, **attrs)}),
                    video.Candidate(video.DASH, url), url, None, env.temp / 'v.part', 30, 'media'))
    assert len(calls) == 1 and 'ffmpeg fetches the stream instead' in caplog.text


def test_aes_keys_and_range_resources_are_fetched_once_with_attributes_preserved():
    key = '#EXT-X-KEY:METHOD=AES-128,URI="key.bin?sig=secret",IV=0x00000000000000000000000000000001,KEYFORMAT="identity"'
    text = ('#EXTM3U\n' + key + '\n#EXTINF:1,\n#EXT-X-BYTERANGE:100@200\nall.ts\n'
            + key + '\n#EXTINF:1,\n#EXT-X-BYTERANGE:100@0\nall.ts\n#EXT-X-KEY:METHOD=NONE\n'
            '#EXTINF:1,\n#EXT-X-BYTERANGE:100\nall.ts\n#EXT-X-ENDLIST\n')
    plan = video.local_playlist(text, 'https://cdn.example/v/media.m3u8', 'v')
    assert plan.files == [('https://cdn.example/v/key.bin?sig=secret', 'v_key0.bin'),
                          ('https://cdn.example/v/all.ts', 'v00000.ts')]
    assert plan.text.count('URI="v_key0.bin"') == 2
    assert 'IV=0x00000000000000000000000000000001,KEYFORMAT="identity"' in plan.text
    assert '#EXT-X-BYTERANGE:100@200' in plan.text and '#EXT-X-BYTERANGE:100\n' in plan.text
    assert plan.text.count('\nv00000.ts\n') == 3 and 'secret' not in plan.text


@pytest.mark.parametrize('kind', ['aes', 'dash'])
@pytest.mark.parametrize('resume', [True, False])
def test_more_stream_types_resume_completed_files(resume_env, monkeypatch, kind, resume):
    e = resume_env
    e.stub.auto_resume = resume
    if kind == 'aes':
        text = ('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin",IV=0x01\n'
                '#EXTINF:1,\n0.ts\n#EXTINF:1,\n1.ts\n#EXTINF:1,\n2.ts\n#EXT-X-ENDLIST\n')
        e.playlists = video.local_playlist(text, 'https://cdn.example/v/', 'v'), None
    else:
        mpd = dash_mpd('<Period><AdaptationSet mimeType="video/mp4">' + dash_rep(
            '<SegmentList><Initialization sourceURL="init.mp4"/><SegmentURL media="0.ts"/>'
            '<SegmentURL media="1.ts"/><SegmentURL media="2.ts"/></SegmentList>')
            + '</AdaptationSet></Period>')
        e.playlists = video.local_dash(mpd, 'https://cdn.example/m.mpd')
    async def join(cmd, temp, timeout, what, cwd=None):
        temp.write_bytes(b'joined')
    monkeypatch.setattr(e.manager, '_run_cmd', join)
    e.failure = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        parallel_run(e)
    assert e.folder.exists() == resume
    if resume:
        assert (e.folder / e.playlists[0].files[0][1]).read_bytes() == b'ab'
    e.failure = None
    e.calls.clear()
    parallel_run(e)
    expected = e.playlists[0].files[2:] if resume else e.playlists[0].files
    assert e.calls == [url for url, _ in expected]
    assert e.tempfile.read_bytes() == b'joined' and not e.folder.exists()


@pytest.mark.parametrize('kind', ['aes', 'dash'])
def test_changed_key_or_representation_invalidates_resume(resume_env, monkeypatch, kind):
    e = resume_env
    if kind == 'aes':
        text = '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n#EXTINF:1,\n0.ts\n#EXTINF:1,\n1.ts\n#EXT-X-ENDLIST\n'
        old = video.local_playlist(text, 'https://cdn.example/', 'v')
        new = video.local_playlist(text.replace('key.bin', 'other.bin'), 'https://cdn.example/', 'v')
    else:
        text = dash_mpd('<Period><AdaptationSet mimeType="video/mp4">' + dash_rep(
            '<SegmentList><SegmentURL media="0.ts"/><SegmentURL media="1.ts"/></SegmentList>') + '</AdaptationSet></Period>')
        old = video.local_dash(text, 'https://cdn.example/m.mpd')[0]
        new = video.local_dash(text.replace('id="high"', 'id="changed"'), 'https://cdn.example/m.mpd')[0]
    e.playlists = old, None
    async def join(*args, **kwargs):
        e.tempfile.write_bytes(b'joined')
    monkeypatch.setattr(e.manager, '_run_cmd', join)
    e.failure = OSError('stop')
    with pytest.raises(stream_mod.SegmentError):
        parallel_run(e)
    e.failure = None
    e.calls.clear()
    parallel_run(e, (new, None))
    assert e.calls == [url for url, _ in new.files]


def packet_hashes(path):
    return subprocess.run([FFMPEG, '-v', 'error', '-i', str(path), '-map', '0', '-c', 'copy',
                           '-f', 'streamhash', '-hash', 'sha256', '-'], capture_output=True, check=True).stdout


@needs_ffmpeg
@pytest.mark.parametrize('kind', ['aes', 'ranges', 'dash'])
def test_more_streams_join_locally_with_real_ffmpeg(env, tmp_path, monkeypatch, kind):
    # The fake session yields real media bytes; the manager uses real ffmpeg.
    source = tmp_path / 'source'
    source.mkdir()
    if kind == 'dash':
        ffmpeg_make(['-f', 'dash', '-seg_duration', '1', '-use_template', '1',
                     '-use_timeline', '1', 'movie.mpd'], source)
        mpd = (source / 'movie.mpd').read_text()
        plans = video.local_dash(mpd, 'https://cdn.example/movie.mpd')
        # The reference is each stream's segments joined as the muxer wrote
        # them, not ffmpeg reading movie.mpd: ffmpeg 6.1's DASH reader drops
        # audio packets that the segments hold
        inputs = []
        for n in range(2):
            stream = f'stream{n}.mp4'
            parts = [f'init-stream{n}.m4s', *sorted(p.name for p in source.glob(f'chunk-stream{n}-*.m4s'))]
            (source / stream).write_bytes(b''.join((source / p).read_bytes() for p in parts))
            inputs += ['-i', stream]
        subprocess.run([FFMPEG, '-v', 'error', '-y', *inputs, '-map', '0', '-map', '1',
                        '-c', 'copy', 'plain.mp4'], cwd=source, capture_output=True, check=True)
    else:
        segments = make_segments(tmp_path, 'segments', '-bsf:v', 'dump_extra=freq=keyframe')
        for name, body in segments.items():
            (source / name).write_bytes(body)
        plain = media_playlist(list(segments)).decode()
        (source / 'plain.m3u8').write_text(plain)
        subprocess.run(video.local_join_command(FFMPEG, 'plain.m3u8', 'plain.mp4'),
                       cwd=source, capture_output=True, check=True)
        if kind == 'ranges':
            # Out-of-order storage: byte ranges must be read, not all bytes copied.
            stored = list(reversed(list(segments)))
            offsets, data = {}, b''
            for name in stored:
                offsets[name] = len(data)
                data += segments[name]
            (source / 'all.ts').write_bytes(data)
            text = '#EXTM3U\n#EXT-X-TARGETDURATION:1\n'
            for name, body in segments.items():
                text += f'#EXTINF:1,\n#EXT-X-BYTERANGE:{len(body)}@{offsets[name]}\nall.ts\n'
            text += '#EXT-X-ENDLIST\n'
        else:
            key, iv = bytes(range(16)), bytes(reversed(range(16)))
            (source / 'key.bin').write_bytes(key)
            tag = f'#EXT-X-KEY:METHOD=AES-128,URI="key.bin",IV=0x{iv.hex()}\n'
            text = plain.replace('#EXTINF:', tag + '#EXTINF:')
            for name, body in segments.items():
                subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'data', '-i', 'pipe:0',
                                '-map', '0', '-c', 'copy', '-f', 'data',
                                '-encryption_key', key.hex(), '-encryption_iv', iv.hex(),
                                'crypto:' + name], input=body, cwd=source,
                               capture_output=True, check=True)
        plans = video.local_playlist(text, 'https://cdn.example/media.m3u8', 'v'), None
    bodies = {url: (source / urlparse(url).path.rsplit('/', 1)[-1]).read_bytes()
              for plan in plans if plan for url, _ in plan.files}
    seen, active, peak = [], 0, 0
    @contextlib.asynccontextmanager
    async def request(url=None, **kwargs):
        nonlocal active, peak
        seen.append((url, kwargs))
        active += 1
        peak = max(peak, active)
        body = bodies[url]
        class Response:
            ok, status = True, 200
            headers = {'content-length': str(len(body))}
            async def iter_chunked(self, size):
                await asyncio.sleep(0.01)
                yield body
        try:
            yield Response()
        finally:
            active -= 1
    monkeypatch.setattr(stream_mod, 'segment_limit', lambda: 3)
    out = env.temp / 'joined.part'
    manager = stream_mod.FanslyStreamDownloadManager()
    asyncio.run(manager._parallel_copy(SimpleNamespace(requests_async=request), plans, out, TEST_SIGNED, 30))
    assert peak > 1 or kind == 'ranges'
    assert len(seen) == len(bodies)  # keys and range resources are fetched just once
    assert all(kwargs['cookies'] == TEST_SIGNED for _, kwargs in seen)
    assert packet_hashes(out) == packet_hashes(source / 'plain.mp4')
    assert sorted(s['codec_type'] for s in probe(out)['streams']) == ['audio', 'video']
    assert not stream_mod.segment_folder(out).exists()


def test_video_and_audio_share_one_key_fetch(env):
    text = '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n#EXTINF:1,\ntrack.ts\n#EXT-X-ENDLIST\n'
    session = FakeSession({'https://cdn.example/video.m3u8': text,
                           'https://cdn.example/audio.m3u8': text.replace('track.ts', 'audio.ts')})
    v, a = asyncio.run(stream_mod.FanslyStreamDownloadManager()._local_playlists(
        session, 'https://cdn.example/video.m3u8', 'https://cdn.example/audio.m3u8', {}, 'media'))
    assert [url for plan in (v, a) for url, _ in plan.files].count('https://cdn.example/key.bin') == 1
    assert 'URI="v_key0.bin"' in v.text and 'URI="v_key0.bin"' in a.text


def test_map_byte_range_attributes_are_preserved():
    plan = video.local_playlist('#EXTM3U\n#EXT-X-MAP:URI="all.mp4",BYTERANGE="200@0"\n'
                                '#EXTINF:1,\n#EXT-X-BYTERANGE:400@200\nall.mp4\n#EXT-X-ENDLIST\n',
                                'https://cdn.example/v.m3u8', 'v')
    assert len(plan.files) == 1
    assert '#EXT-X-MAP:URI="vinit00000.mp4",BYTERANGE="200@0"' in plan.text
    assert '#EXT-X-BYTERANGE:400@200\nvinit00000.mp4' in plan.text


def test_dash_refreshed_signatures_do_not_invalidate_resume(resume_env, monkeypatch):
    e = resume_env
    mpd = dash_mpd('<Period><AdaptationSet mimeType="video/mp4">' + dash_rep(
        '<SegmentTemplate initialization="init.mp4?sig=old" media="$Number$.ts?sig=old" duration="1" startNumber="0"/>')
        + '</AdaptationSet></Period>')
    e.playlists = video.local_dash(mpd, 'https://cdn.example/m.mpd')
    async def join(*args, **kwargs):
        e.tempfile.write_bytes(b'joined')
    monkeypatch.setattr(e.manager, '_run_cmd', join)
    e.failure = OSError('stop')
    with pytest.raises(stream_mod.SegmentError):
        parallel_run(e)
    assert 'sig=' not in (e.folder / 'manifest.json').read_text()
    e.failure = None
    e.calls.clear()
    refreshed = video.local_dash(mpd.replace('sig=old', 'sig=new'), 'https://cdn.example/m.mpd')
    parallel_run(e, refreshed)
    assert e.calls == [url for url, _ in refreshed[0].files[2:]]


import sys as _sys

# a child process that really crashes: Python turns a bad memory read into an
# exception on Windows, so fail fast there
CRASH = (
    "import ctypes; ctypes.windll.kernel32.RaiseFailFastException(None, None, 0)"
    if _sys.platform == "win32"
    else "import faulthandler; faulthandler._sigsegv()"
)


@pytest.mark.parametrize(
    "code,said",
    [
        # a crash (as a static ffmpeg does on some newer Linux systems)
        (CRASH, "crashed ("),
        ("import sys; sys.exit(3)", "exited with code 3 without a message"),
        ("pass", "finished, but its output file is missing or empty"),
    ],
)
def test_a_silent_ffmpeg_failure_says_how_it_ended(env, code, said):
    import sys

    temp = env.temp / "x.part"
    cmd = [sys.executable, "-I", "-c", code]
    with pytest.raises(Exception) as caught:
        asyncio.run(stream_mod.FanslyStreamDownloadManager()._run_cmd(
            cmd, temp, 60, "join the stream's segments"))
    message = str(caught.value)
    assert message.startswith(f"ffmpeg could not join the stream's segments: {sys.executable} ")
    assert said in message


def test_a_crash_after_a_message_says_both(env):
    import sys

    temp = env.temp / "x.part"
    code = "import sys; sys.stderr.write('some last words\\n'); sys.stderr.flush(); " + CRASH
    with pytest.raises(Exception) as caught:
        asyncio.run(stream_mod.FanslyStreamDownloadManager()._run_cmd(
            [sys.executable, "-I", "-c", code], temp, 60, "join the stream's segments"))
    message = str(caught.value)
    assert "crashed (" in message
    assert "some last words" in message
