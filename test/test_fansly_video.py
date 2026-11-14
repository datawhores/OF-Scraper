"""Fansly video: best delivery, HLS and DASH through ffmpeg, re-runs.

The account-media fixture is a sanitised capture. No master playlist or MPD
was captured, so the ones used here are written by the tests.
"""

import asyncio
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

import pytest

import ofscraper.commands.db as db_command
import ofscraper.commands.metadata.manager as meta_mod
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.fansly_stream_download as stream_mod
import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.filters.media.filters as filters
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
        "size_min": 0, "force_all": False, "force_model_unique": False, "download_sems": 2,
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


def ffmpeg_make(args, cwd):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=3",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
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


def make_segments(tmp_path, name, *args):
    """{file name: bytes} of 1-second MPEG-TS segments made by ffmpeg."""
    seg_dir = tmp_path / name
    seg_dir.mkdir()
    ffmpeg_make([*args, "-f", "segment", "-segment_time", "1", "-segment_format", "mpegts",
                 f"{name}-%d.ts"], seg_dir)
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
    '#EXT-X-STREAM-INF:BANDWIDTH=400000,RESOLUTION=640x360,CODECS="avc1.64001e,mp4a.40.2",AUDIO="aud"\n'
    "r360/media.m3u8\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=9000000,RESOLUTION=3840x2160,CODECS="avc1.640033,mp4a.40.2",AUDIO="aud"\n'
    "r2160/media.m3u8\n"
)


def ffmpeg_only(monkeypatch):
    """Leave the stream to ffmpeg alone, as with FANSLY_STREAM_SEGMENTS=0."""
    monkeypatch.setattr(stream_mod, "segment_limit", lambda: 0)


def fast_retries(monkeypatch, attempts=2):
    """The download retries without their waits."""
    from tenacity import stop_after_attempt, wait_none

    real = stream_mod.download_retry
    monkeypatch.setattr(stream_mod, "download_retry",
                        lambda: real(stop=stop_after_attempt(attempts), wait=wait_none()))


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
    assert join[join.index("-protocol_whitelist") + 1] == "file"
    assert not any("http" in str(a) for a in join)


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
    assert files_in(env.out, env.temp) == [] and list(env.temp.iterdir()) == []
    assert env.marks == [] and len(env.ffmpeg_runs) == (1 if path == "ffmpeg" else 0)


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
def test_a_segment_that_fails_every_retry_fails_the_file_and_removes_the_segments(env, tmp_path, monkeypatch):
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
    assert list(env.out.iterdir()) == [] and list(env.temp.iterdir()) == []
    assert env.marks == [] and env.ffmpeg_runs == []


@needs_ffmpeg
def test_cancelled_parallel_download_removes_the_segments(env, tmp_path):
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
    assert list(env.out.iterdir()) == [] and list(env.temp.iterdir()) == []
    assert env.marks == [] and env.ffmpeg_runs == []


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
    assert list(env.out.iterdir()) == [] and list(env.temp.iterdir()) == []


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
    "encrypted": "#EXT-X-KEY:METHOD=AES-128,URI=\"k.key\"\n",
    "sample_aes": "#EXT-X-KEY:METHOD=SAMPLE-AES,URI=\"k.key\"\n",
    "byterange": "#EXT-X-BYTERANGE:1000@0\n",
    "map_byterange": '#EXT-X-MAP:URI="i.mp4",BYTERANGE="100@0"\n',
    "nested": '#EXT-X-STREAM-INF:BANDWIDTH=1\n',
    "partial": '#EXT-X-PART:DURATION=1,URI="p.m4s"\n',
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


@pytest.mark.parametrize("case", ["encrypted", "byterange", "no_endlist"])
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
    assert join[join.index("-i") + 1] == "video.m3u8"
    assert [a for a in join if str(a).endswith(".m3u8")] == ["video.m3u8", "audio.m3u8"]
    assert list(hashed.iterdir()) == []


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
    assert list(env.out.iterdir()) == [] and list(env.temp.iterdir()) == []


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
