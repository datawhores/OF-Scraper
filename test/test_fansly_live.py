"""Fansly livestream recording: detection, ffmpeg recording, restarts, watch mode, chat.

No request goes to Fansly. API answers are synthesised from the spec, and the
"live" HLS stream is served by a local test server from segments ffmpeg makes.
"""

import asyncio
import contextlib
import http.server
import json
import pathlib
import shutil
import subprocess
import threading
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import pytest

import ofscraper.commands.scraper.scraper as scraper
import ofscraper.managers.manager as manager
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.system.ffmpeg as ffmpeg_finder
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import live, live_api, live_chat

TOKEN = "a" * 60
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/140.0"
STARTED_MS = 1760000000123  # 2025-10-09 08:53:20 UTC
STAMP = "20251009_085320"
CREATOR_A = ("100000000000000101", "creator_a")
CREATOR_B = ("100000000000000102", "creator_b")
CREATOR_C = ("100000000000000103", "creator_c")

# the local test server is plain http; the app allows https only
LOCAL = ("http", "https")

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not on PATH")


# ------------------------------------------------------------------ synthetic API answers

def online_response(*creators):
    return {
        "success": True,
        "response": {
            "streams": [
                {"id": f"9{aid[1:]}", "channelId": f"8{aid[1:]}", "accountId": aid,
                 "title": f"{name} stream", "status": 2, "viewerCount": 3,
                 "startedAt": STARTED_MS}
                for aid, name in creators
            ],
            "aggregationData": {
                "accounts": [
                    {"id": aid, "username": name,
                     "streaming": {"accountId": aid, "enabled": True,
                                   "channel": {"id": f"8{aid[1:]}", "accountId": aid, "status": 2}}}
                    for aid, name in creators
                ]
            },
        },
    }


def channel_response(aid, playback_url, status=2):
    return {
        "success": True,
        "response": {
            "id": f"8{aid[1:]}", "accountId": aid, "chatRoomId": f"7{aid[1:]}",
            "playbackUrl": "https://example.invalid/unauthenticated.m3u8", "status": status,
            "stream": {"id": f"9{aid[1:]}", "historyId": "1", "channelId": f"8{aid[1:]}",
                       "accountId": aid, "title": "a stream", "status": status,
                       "viewerCount": 3, "startedAt": STARTED_MS, "playbackUrl": playback_url},
        },
    }


MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=1280x720,CODECS="avc1.4d401f,mp4a.40.2"
720p30/playlist.m3u8?vt=hi
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2"
https://cdn.example.invalid/v1/1080p60/playlist.m3u8?vt=best
#EXT-X-STREAM-INF:BANDWIDTH=300000,RESOLUTION=640x360,CODECS="avc1.4d401e,mp4a.40.2"
360p30/playlist.m3u8?vt=lo
"""


# ------------------------------------------------------------------ fakes for the app session

class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status

    async def json_(self):
        return self.body

    async def text_(self):
        return self.body if isinstance(self.body, str) else json.dumps(self.body)


class FakeClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        self.calls.append((url, kwargs.get("actions")))
        for prefix, answer in self.routes.items():
            if url.startswith(prefix):
                body = answer(url) if callable(answer) else answer
                yield FakeResponse(body)
                return
        raise AssertionError(f"unexpected request {url}")


@pytest.fixture
def fansly_settings(monkeypatch, tmp_path):
    def apply(**values):
        real = settings.get_settings()
        stub = SimpleNamespace(**{**dict(real), "site": "fansly", "usernames": None,
                                  "excluded_username": None, "live": False, "live_watch": False,
                                  "live_interval": None, "live_max": None, "live_chat": False,
                                  **values})
        monkeypatch.setattr(settings, "get_settings", lambda: stub)
        return stub

    monkeypatch.setattr(fansly_auth, "read_auth",
                        lambda path=None: {"authorization_token": TOKEN, "user_agent": UA})
    monkeypatch.setattr(common_paths, "get_save_location", lambda config=None: str(tmp_path))
    monkeypatch.setattr(ffmpeg_finder, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(live, "_warned", False)
    return apply


def install_session(monkeypatch, client):
    @contextlib.asynccontextmanager
    async def aget_ofsession(*args, **kwargs):
        yield client

    monkeypatch.setattr(manager, "Manager",
                        SimpleNamespace(session=SimpleNamespace(aget_ofsession=aget_ofsession)))


# ------------------------------------------------------------------ DoD 1

def test_selected_live_creator_gets_a_fresh_url_and_ffmpeg_on_the_best_variant(
        monkeypatch, tmp_path, fansly_settings):
    fansly_settings(live=True, usernames=("creator_a",))
    order = []
    tokens = iter(["tok1", "tok2"])

    def channel(url):
        order.append("channel")
        return channel_response(CREATOR_A[0], f"https://live.example.invalid/a/master.m3u8?token={next(tokens)}")

    def online(url):
        order.append("online")
        return online_response(CREATOR_A, CREATOR_B)

    def playlist(url):
        order.append(url)
        if "master.m3u8" in url:
            return MASTER
        return "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2.0,\ns1.ts\n#EXT-X-ENDLIST\n"

    client = FakeClient({
        live_api.ONLINE_URL: online,
        live_api.channel_url(CREATOR_A[0]): channel,
        "https://live.example.invalid/": playlist,
        "https://cdn.example.invalid/": playlist,
    })
    install_session(monkeypatch, client)
    commands = []

    async def fake_ffmpeg(cmd, stop=None):
        order.append("ffmpeg")
        commands.append(cmd)
        with open(cmd[-1], "wb") as f:
            f.write(b"\0" * 32)
        return 0

    monkeypatch.setattr(live, "run_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(live_chat, "aiohttp_connect",
                        lambda *a, **k: pytest.fail("chat must stay off by default"))

    asyncio.run(live.run(watch=False))

    # online first, then a fresh channel fetch right before the master playlist and ffmpeg
    assert order[:4] == ["online", "channel",
                         "https://live.example.invalid/a/master.m3u8?token=tok1", "ffmpeg"]
    assert len(commands) == 1  # creator_b is live but not selected
    cmd = commands[0]
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-i") + 1] == "https://cdn.example.invalid/v1/1080p60/playlist.m3u8?vt=best"
    assert cmd[cmd.index("-c") + 1] == "copy"
    assert "Origin: https://fansly.com" in cmd[cmd.index("-headers") + 1]
    expected = tmp_path / "Fansly" / "creator_a" / "Livestreams" / f"creator_a_{STAMP}_live.mp4"
    assert cmd[-1] == str(expected)
    sidecar = json.loads(expected.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["streamId"] == f"9{CREATOR_A[0][1:]}"
    assert sidecar["channelId"] == f"8{CREATOR_A[0][1:]}"
    assert sidecar["parts"] == [expected.name]
    assert sidecar["chat"] is None
    # playlists went through the CDN routing (headers only: no signing, no cookies)
    cdn_calls = [a for u, a in client.calls if "example.invalid" in u]
    assert cdn_calls and all(a == ["create_header"] for a in cdn_calls)


def test_master_playlist_parsing_picks_highest_bandwidth():
    variants = live.parse_master(MASTER, "https://live.example.invalid/a/master.m3u8?token=x")
    assert [v["bandwidth"] for v in variants] == [900000, 2500000, 300000]
    assert variants[0]["uri"] == "https://live.example.invalid/a/720p30/playlist.m3u8?vt=hi"
    assert live.pick_variant(variants)["uri"].endswith("1080p60/playlist.m3u8?vt=best")


def test_selection_follows_usernames_and_exclusions():
    online = live_api.parse_online(online_response(CREATOR_A, CREATOR_B, CREATOR_C))
    assert [s["username"] for s in live.select_streams(online)] == ["creator_a", "creator_b", "creator_c"]
    assert [s["username"] for s in live.select_streams(online, ["ALL"], ["creator_b"])] == ["creator_a", "creator_c"]
    assert [s["username"] for s in live.select_streams(online, ["Creator_C"])] == ["creator_c"]


def test_selection_matches_account_ids():
    online = live_api.parse_online(online_response(CREATOR_A, CREATOR_B, CREATOR_C))
    # -u <account id> selects that creator
    assert [s["username"] for s in live.select_streams(online, [CREATOR_B[0]])] == ["creator_b"]
    # -eu <account id> excludes it, with or without -u
    assert [s["username"] for s in live.select_streams(online, None, [CREATOR_B[0]])] == ["creator_a", "creator_c"]
    assert [s["username"] for s in live.select_streams(online, ["ALL"], [CREATOR_B[0]])] == ["creator_a", "creator_c"]
    assert live.select_streams(online, [CREATOR_B[0]], [CREATOR_B[0]]) == []
    # names and ids mixed
    assert [s["username"] for s in live.select_streams(online, ["creator_a", CREATOR_C[0]])] == ["creator_a", "creator_c"]


def test_selection_matches_an_id_the_api_sent_as_a_number():
    online = live_api.parse_online({
        "success": True,
        "response": {
            "streams": [{"id": 1, "channelId": 2, "accountId": 100000000000000104, "status": 2}],
            "aggregationData": {"accounts": [{"id": 100000000000000104, "username": "creator_d"}]},
        },
    })
    assert [s["username"] for s in live.select_streams(online, ["100000000000000104"])] == ["creator_d"]
    assert live.select_streams(online, None, ["100000000000000104"]) == []
    # an int on the stream entry itself compares the same
    raw = [{"accountId": 100000000000000104, "username": "creator_d"}]
    assert live.select_streams(raw, ["100000000000000104"]) == raw
    assert live.select_streams(raw, None, ["100000000000000104"]) == []


def test_selection_by_name_is_unchanged_for_mixed_case_names():
    mixed = ("100000000000000105", "MixedCreator")
    online = live_api.parse_online(online_response(CREATOR_A, mixed))
    for name in ("mixedcreator", "MixedCreator", "MIXEDCREATOR"):
        assert [s["username"] for s in live.select_streams(online, [name])] == ["MixedCreator"]
        assert [s["username"] for s in live.select_streams(online, None, [name])] == ["creator_a"]
    assert live.select_streams(online, ["nosuchcreator"]) == []


@pytest.mark.parametrize("watch", [False, True], ids=["live", "live-watch"])
def test_live_and_live_watch_record_a_creator_selected_by_account_id(
        monkeypatch, tmp_path, fansly_settings, watch):
    fansly_settings(live=not watch, live_watch=watch, usernames=(CREATOR_B[0],))
    client = FakeClient({
        live_api.ONLINE_URL: online_response(CREATOR_A, CREATOR_B),
        live_api.channel_url(CREATOR_B[0]): channel_response(
            CREATOR_B[0], "https://live.example.invalid/b/playlist.m3u8?token=t"),
        "https://live.example.invalid/": "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2.0,\ns1.ts\n#EXT-X-ENDLIST\n",
    })
    install_session(monkeypatch, client)
    recorded = []

    async def main():
        stop = asyncio.Event()

        async def fake_ffmpeg(cmd, stop_event=None):
            recorded.append(cmd[-1])
            with open(cmd[-1], "wb") as f:
                f.write(b"\0" * 32)
            if watch:
                stop.set()  # watch mode runs until stopped
            return 0

        monkeypatch.setattr(live, "run_ffmpeg", fake_ffmpeg)
        await asyncio.wait_for(live.run(watch=watch, stop=stop), timeout=30)

    asyncio.run(main())
    assert len(recorded) == 1
    assert pathlib.Path(recorded[0]).parent == tmp_path / "Fansly" / "creator_b" / "Livestreams"


# ------------------------------------------------------------------ local live HLS server

@pytest.fixture(scope="module")
def segments(tmp_path_factory):
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg/ffprobe not on PATH")
    folder = tmp_path_factory.mktemp("hls")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
         "-t", "6", "-c:v", "libx264", "-g", "10", "-c:a", "aac",
         "-f", "hls", "-hls_time", "1", "-hls_list_size", "0",
         "-hls_segment_filename", str(folder / "seg%d.ts"), str(folder / "src.m3u8")],
        check=True, timeout=120)
    files = sorted(folder.glob("seg*.ts"), key=lambda p: int(p.stem[3:]))
    return [p.read_bytes() for p in files]


class LiveHLS:
    """A growing live playlist: one more segment per reload, then ENDLIST.

    ``valid`` holds the playback tokens the master accepts. A variant token
    listed in ``expire_after`` answers 403 after that many reloads.
    """

    def __init__(self, segs, window=3):
        self.segs = segs
        self.window = window
        self.published = 2
        self.valid = set()
        self.expire_after = {}
        self.reloads = {}
        self.log = []
        self.lock = threading.Lock()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, body=b"", ctype="application/vnd.apple.mpegurl"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                code, body, ctype = server.answer(self.path, dict(self.headers))
                self._send(code, body, ctype)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def master_url(self, token):
        return f"{self.base}/live/master.m3u8?token={token}"

    def _expired(self, vt):
        limit = self.expire_after.get(vt)
        return limit is not None and self.reloads.get(vt, 0) > limit

    def answer(self, path, headers):
        u = urlparse(path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        with self.lock:
            self.log.append((u.path, q, headers.get("Origin")))
            if u.path == "/live/master.m3u8":
                token = q.get("token")
                if token not in self.valid:
                    return 403, b"", "text/plain"
                body = ("#EXTM3U\n"
                        "#EXT-X-STREAM-INF:BANDWIDTH=200000,RESOLUTION=160x90\n"
                        f"low.m3u8?vt={token}\n"
                        "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=160x90\n"
                        f"high.m3u8?vt={token}\n")
                return 200, body.encode(), "application/vnd.apple.mpegurl"
            if u.path in ("/live/high.m3u8", "/live/low.m3u8"):
                vt = q.get("vt")
                self.reloads[vt] = self.reloads.get(vt, 0) + 1
                if vt not in self.valid or self._expired(vt):
                    return 403, b"", "text/plain"
                ended = self.published >= len(self.segs)
                n = self.published
                self.published = min(self.published + 1, len(self.segs))
                first = max(0, n - self.window)
                body = ("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n"
                        f"#EXT-X-MEDIA-SEQUENCE:{first}\n")
                for i in range(first, n):
                    body += f"#EXTINF:1.0,\nseg{i}.ts?vt={vt}\n"
                if ended:
                    body += "#EXT-X-ENDLIST\n"
                return 200, body.encode(), "application/vnd.apple.mpegurl"
            if u.path.startswith("/live/seg"):
                vt = q.get("vt")
                if vt not in self.valid or self._expired(vt):
                    return 403, b"", "text/plain"
                i = int(u.path[len("/live/seg"):-len(".ts")])
                return 200, self.segs[i], "video/mp2t"
            return 404, b"", "text/plain"


@pytest.fixture
def hls(segments):
    server = LiveHLS(segments)
    yield server
    server.close()


async def http_text(url):
    def get():
        try:
            with urlopen(url, timeout=10) as r:
                return r.read().decode()
        except HTTPError as e:
            # an HTTPError is an open response too; Python 3.14+ warns if it isn't closed
            e.close()
            raise

    return await asyncio.to_thread(get)


def channel_feed(server, tokens, live_until=None):
    """fetch_channel: each call hands out the next fresh playback token."""
    calls = []

    async def fetch_channel():
        calls.append(len(calls) + 1)
        token = tokens[min(len(calls), len(tokens)) - 1]
        server.valid.add(token)
        status = 2 if live_until is None or len(calls) <= live_until else 0
        return live_api.parse_channel(
            channel_response(CREATOR_A[0], server.master_url(token), status=status))

    return fetch_channel, calls


def stream_a():
    return live_api.parse_online(online_response(CREATOR_A))[0]


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


# ------------------------------------------------------------------ DoD 2

@needs_ffmpeg
def test_growing_live_playlist_then_endlist_gives_one_playable_mp4(hls, tmp_path):
    fetch_channel, calls = channel_feed(hls, ["t1"])
    rec = live.LiveRecorder(stream_a(), tmp_path, fetch_channel, http_text,
                            ffmpeg="ffmpeg", backoff=(0, 0), schemes=LOCAL)
    sidecar = asyncio.run(asyncio.wait_for(rec.run(), timeout=120))

    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    mp4 = folder / f"creator_a_{STAMP}_live.mp4"
    assert sorted(p.name for p in folder.iterdir()) == sorted([mp4.name, f"creator_a_{STAMP}_live.json"])
    info = probe(mp4)
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    assert float(info["format"]["duration"]) >= 5  # all six one-second segments
    assert sidecar["parts"] == [mp4.name]
    assert sidecar["endReason"] == "stream ended"
    assert json.loads((folder / f"creator_a_{STAMP}_live.json").read_text(encoding="utf-8")) == sidecar
    assert calls == [1]
    # only the highest-bandwidth variant was recorded
    assert not any(p == "/live/low.m3u8" for p, _, _ in hls.log)
    # ffmpeg sends the browser Origin with its segment requests
    seg_origins = {origin for p, _, origin in hls.log if p.startswith("/live/seg")}
    assert seg_origins == {"https://fansly.com"}


# ------------------------------------------------------------------ DoD 3

@needs_ffmpeg
def test_403_mid_stream_refreshes_the_url_and_continues_into_part2(hls, tmp_path):
    hls.expire_after = {"t1": 2}  # the first token dies after two playlist reloads
    fetch_channel, calls = channel_feed(hls, ["t1", "t2"])
    rec = live.LiveRecorder(stream_a(), tmp_path, fetch_channel, http_text,
                            ffmpeg="ffmpeg", backoff=(0, 0), schemes=LOCAL)
    sidecar = asyncio.run(asyncio.wait_for(rec.run(), timeout=120))

    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    part1 = folder / f"creator_a_{STAMP}_live.mp4"
    part2 = folder / f"creator_a_{STAMP}_live_part2.mp4"
    assert calls == [1, 2]  # one refresh
    assert sidecar["parts"] == [part1.name, part2.name]
    assert sidecar["endReason"] == "stream ended"
    for part in (part1, part2):
        assert float(probe(part)["format"]["duration"]) > 0


@needs_ffmpeg
def test_repeated_403_after_refresh_stops_cleanly_at_the_limit(hls, tmp_path):
    hls.expire_after = {"t1": 2}
    fetch_channel, calls = channel_feed(hls, ["t1", "t2"])
    hls.expire_after["t2"] = 0  # the fresh URL is refused too

    rec = live.LiveRecorder(stream_a(), tmp_path, fetch_channel, http_text,
                            ffmpeg="ffmpeg", backoff=(0, 0), schemes=LOCAL, max_failures=3)
    sidecar = asyncio.run(asyncio.wait_for(rec.run(), timeout=120))

    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    assert calls == [1, 2, 3, 4]  # first start, then three refreshes that all fail
    assert sidecar["parts"] == [f"creator_a_{STAMP}_live.mp4"]
    assert sidecar["endReason"] == "stopped after 3 failed attempts"
    # no empty part files are left behind
    assert sorted(p.name for p in folder.glob("*.mp4")) == sidecar["parts"]


def test_restart_logic_without_ffmpeg(tmp_path):
    """Same rules with fakes: drop -> fresh URL -> part2; not live -> stop."""
    urls = []

    async def fetch_channel():
        n = len(urls) + 1
        urls.append(n)
        return live_api.parse_channel(channel_response(
            CREATOR_A[0], f"https://live.example.invalid/m.m3u8?token=t{n}", status=2 if n < 3 else 0))

    async def fetch_text(url):
        if "m.m3u8" in url:
            return MASTER.replace("https://cdn.example.invalid/v1/", "")
        raise live.PlaylistError("403")  # the variant is gone after each run

    async def fake_ffmpeg(cmd, stop=None):
        with open(cmd[-1], "wb") as f:
            f.write(b"x")
        return 0

    rec = live.LiveRecorder(stream_a(), tmp_path, fetch_channel, fetch_text,
                            ffmpeg_runner=fake_ffmpeg, backoff=(0, 0))
    sidecar = asyncio.run(rec.run())
    assert urls == [1, 2, 3]
    assert sidecar["parts"] == [f"creator_a_{STAMP}_live.mp4", f"creator_a_{STAMP}_live_part2.mp4"]
    assert sidecar["endReason"] == "not live"


def test_backoff_is_bounded():
    rec = live.LiveRecorder(stream_a(), ".", None, None, backoff=(2, 30))
    assert [rec._backoff_delay(n) for n in (1, 2, 3, 4, 5, 9)] == [2, 4, 8, 16, 30, 30]


# ------------------------------------------------------------------ DoD 4

def test_watch_mode_records_at_most_the_limit_and_starts_the_next_when_one_ends():
    streams = live_api.parse_online(online_response(CREATOR_A, CREATOR_B, CREATOR_C))

    async def scenario():
        stop = asyncio.Event()
        release = {s["accountId"]: asyncio.Event() for s in streams}
        started, running, peak = [], set(), [0]
        polls = []

        async def fetch_online():
            polls.append(1)
            return [s for s in streams if not release[s["accountId"]].is_set()]

        async def record(stream, stop_event):
            started.append(stream["username"])
            running.add(stream["username"])
            peak[0] = max(peak[0], len(running))
            await release[stream["accountId"]].wait()
            running.discard(stream["username"])

        watcher = live.LiveWatcher(fetch_online, record, max_concurrent=2, interval=1000, jitter=0)
        task = asyncio.ensure_future(watcher.run(stop))
        for _ in range(20):
            await asyncio.sleep(0)
        assert started == ["creator_a", "creator_b"]
        assert running == {"creator_a", "creator_b"}

        release[streams[0]["accountId"]].set()  # creator_a's stream ends
        for _ in range(20):
            await asyncio.sleep(0)
        assert started == ["creator_a", "creator_b", "creator_c"]  # no wait for the next poll
        assert running == {"creator_b", "creator_c"}
        assert len(polls) == 1

        for e in release.values():
            e.set()
        stop.set()
        await asyncio.wait_for(task, timeout=5)
        return peak[0]

    assert asyncio.run(scenario()) == 2


def test_watch_mode_does_not_start_a_creator_twice():
    streams = live_api.parse_online(online_response(CREATOR_A))

    async def scenario():
        stop = asyncio.Event()
        started = []

        async def record(stream, stop_event):
            started.append(stream["username"])
            await stop_event.wait()

        async def fetch_online():
            return streams

        watcher = live.LiveWatcher(fetch_online, record, max_concurrent=2, interval=0.01, jitter=0)
        task = asyncio.ensure_future(watcher.run(stop))
        await asyncio.sleep(0.2)  # many polls while creator_a is still recording
        stop.set()
        await asyncio.wait_for(task, timeout=5)
        return started

    assert asyncio.run(scenario()) == ["creator_a"]


def test_defaults_match_the_brief(fansly_settings):
    fansly_settings()
    opts = live.options()
    assert (opts["interval"], opts["max_concurrent"], opts["chat"]) == (60, 2, False)
    assert live.DEFAULT_JITTER > 0


# ------------------------------------------------------------------ DoD 5

class FakeSocket:
    def __init__(self, incoming):
        self.incoming = asyncio.Queue()
        for frame in incoming:
            self.incoming.put_nowait(frame)
        self.sent = []
        self.closed = False

    async def send(self, frame):
        self.sent.append(frame)

    async def recv(self):
        return await self.incoming.get()

    async def close(self):
        self.closed = True


def service_event(service_id, event):
    return json.dumps({"t": 10000, "d": json.dumps({"serviceId": service_id, "event": json.dumps(event)})})


def chat_frames(room):
    msg1 = {"chatRoomMessage": {"id": "1", "chatRoomId": room, "senderId": "5", "content": "hello"}}
    msg2 = {"chatRoomMessage": {"id": "2", "chatRoomId": room, "senderId": "6", "content": "hi again"}}
    other_room = {"chatRoomMessage": {"id": "3", "chatRoomId": "1", "content": "elsewhere"}}
    return [
        json.dumps({"t": 1, "d": json.dumps({"session": {"id": "1"}})}),
        service_event(46, msg1),
        service_event(45, {"stream": {"id": "1"}}),  # not chat
        service_event(46, other_room),
        json.dumps({"t": 10001, "d": json.dumps([json.loads(service_event(46, msg2))])}),
        json.dumps({"t": 2, "d": "{}"}),
    ]


def test_chat_on_sends_only_auth_and_keepalive_and_writes_jsonl(tmp_path):
    room = "700000000000000101"
    out = tmp_path / "chat.jsonl"

    async def scenario():
        sock = FakeSocket(chat_frames(room))
        stop = asyncio.Event()

        async def connect():
            return sock

        chat = live_chat.ChatRecorder(connect, TOKEN, ping_interval=(0.01, 0.02))
        task = asyncio.ensure_future(chat.run({"chatRoomId": room}, out, stop))
        await asyncio.sleep(0.15)
        stop.set()
        sock.incoming.put_nowait(json.dumps({"t": 2, "d": "{}"}))
        await asyncio.wait_for(task, timeout=5)
        return sock

    sock = asyncio.run(scenario())
    auth = json.dumps({"t": 1, "d": json.dumps({"token": TOKEN, "v": 3})})
    assert sock.sent[0] == auth
    assert sock.sent.count(auth) == 1
    assert set(sock.sent) == {auth, "p"}  # nothing else: no join, alerts, likes or tips
    assert sock.closed
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [line["chatRoomMessage"]["content"] for line in lines] == ["hello", "hi again"]


def test_chat_refuses_any_other_frame():
    async def scenario():
        chat = live_chat.ChatRecorder(None, TOKEN)
        chat.ws = FakeSocket([])
        for frame in ['{"t":46001,"d":"{}"}', '{"t":1,"d":"{\\"token\\":\\"other\\",\\"v\\":3}"}', "x"]:
            with pytest.raises(live_chat.ForbiddenFrame):
                await chat._send(frame)
        return chat.ws.sent

    assert asyncio.run(scenario()) == []


def test_chat_off_opens_no_socket_and_on_records_beside_the_video(tmp_path):
    async def fetch_channel():
        n = len(calls) + 1
        calls.append(n)
        return live_api.parse_channel(channel_response(
            CREATOR_A[0], "https://live.example.invalid/m.m3u8?token=t", status=2 if n == 1 else 0))

    async def fetch_text(url):
        return "#EXTM3U\n#EXTINF:2.0,\ns.ts\n"

    async def fake_ffmpeg(cmd, stop=None):
        with open(cmd[-1], "wb") as f:
            f.write(b"x")
        return 0

    # off: the recorder has no chat, so nothing can connect
    calls = []
    sidecar = asyncio.run(live.LiveRecorder(stream_a(), tmp_path / "off", fetch_channel, fetch_text,
                                            ffmpeg_runner=fake_ffmpeg, backoff=(0, 0)).run())
    assert sidecar["chat"] is None
    assert not list((tmp_path / "off").rglob("*_chat.jsonl"))

    # on: the chat socket runs beside the recording and lands next to it
    calls = []
    connects = []
    sockets = []

    async def connect():
        connects.append(1)
        sock = FakeSocket(chat_frames(f"7{CREATOR_A[0][1:]}"))
        sockets.append(sock)
        return sock

    async def slow_ffmpeg(cmd, stop=None):
        await asyncio.sleep(0.1)  # let chat frames arrive while "recording"
        return await fake_ffmpeg(cmd, stop)

    chat = live_chat.ChatRecorder(connect, TOKEN, ping_interval=(0.01, 0.02))
    sidecar = asyncio.run(live.LiveRecorder(stream_a(), tmp_path / "on", fetch_channel, fetch_text,
                                            ffmpeg_runner=slow_ffmpeg, backoff=(0, 0), chat=chat).run())
    assert connects == [1]
    chat_file = tmp_path / "on" / "Fansly" / "creator_a" / "Livestreams" / f"creator_a_{STAMP}_live_chat.jsonl"
    assert sidecar["chat"] == chat_file.name
    assert len(chat_file.read_text(encoding="utf-8").splitlines()) == 2
    assert set(sockets[0].sent) <= {live_chat.auth_frame(TOKEN), "p"}


# ------------------------------------------------------------------ wiring, and DoD 6 (OnlyFans)

def test_live_options_parse_and_default_off():
    import ofscraper.utils.args.parse.group_bundles.main as main_bundle  # noqa: F401
    from ofscraper.utils.args.parse.arguments import automatic

    names = {"live", "live_watch", "live_interval", "live_max", "live_chat"}
    import click

    @click.command()
    @automatic.live_option
    @automatic.live_watch_option
    @automatic.live_interval_option
    @automatic.live_max_option
    @automatic.live_chat_option
    def cmd(**kwargs):
        cmd.result = kwargs

    cmd.main([], standalone_mode=False)
    assert set(cmd.result) == names
    assert cmd.result == {"live": False, "live_watch": False, "live_interval": None,
                          "live_max": None, "live_chat": False}
    cmd.main(["--live-watch", "--live-interval", "30", "--live-max", "3", "--live-chat"],
             standalone_mode=False)
    assert cmd.result["live_watch"] and cmd.result["live_chat"]
    assert (cmd.result["live_interval"], cmd.result["live_max"]) == (30, 3)


def test_fansly_live_without_actions_records_instead_of_prompting(monkeypatch, fansly_settings):
    fansly_settings(live=True)
    seen = []
    monkeypatch.setattr(settings, "get_args", lambda copy=False: SimpleNamespace(
        daemon=None, actions=[], scrape_paid=False))
    monkeypatch.setattr(scraper, "check_auth", lambda: seen.append("auth"))
    monkeypatch.setattr(scraper, "process_prompts", lambda: seen.append("prompts"))
    monkeypatch.setattr(live, "run_blocking", lambda watch, runner=None: seen.append(("live", watch)))
    scraper.scrapper()
    assert seen == ["auth", ("live", False)]


def test_daemon_watch_runs_beside_the_scheduler(monkeypatch, fansly_settings):
    fansly_settings(live_watch=True)
    seen = []
    monkeypatch.setattr(settings, "get_args", lambda copy=False: SimpleNamespace(
        daemon=5.0, actions=[], scrape_paid=False))
    monkeypatch.setattr(scraper.prompts, "action_prompt", lambda: seen.append("prompt"))
    monkeypatch.setattr(scraper, "daemon_process", lambda: seen.append("daemon"))
    scraper.scrapper()
    assert seen == ["daemon"]  # no action prompt needed when watching for livestreams


def test_live_thread_stops_cleanly():
    async def runner(watch, stop):
        await stop.wait()
        runner.stopped = True

    t = live.LiveThread(True, runner)
    t.start()
    t.stop(timeout=5)
    assert not t.is_alive() and runner.stopped


@pytest.mark.parametrize("flags", [{"live": True}, {"live_watch": True},
                                   {"live": True, "live_watch": True, "live_chat": True}])
def test_onlyfans_profile_ignores_live_options(monkeypatch, fansly_settings, flags):
    fansly_settings(site="onlyfans", **flags)
    seen = []
    monkeypatch.setattr(settings, "get_args", lambda copy=False: SimpleNamespace(
        daemon=None, actions=[], scrape_paid=False))
    monkeypatch.setattr(scraper, "process_prompts", lambda: seen.append("prompts"))
    monkeypatch.setattr(scraper, "check_auth", lambda: seen.append("auth"))
    monkeypatch.setattr(live, "run_blocking", lambda *a, **k: seen.append("live"))
    monkeypatch.setattr(live, "run", lambda *a, **k: pytest.fail("no livestream calls on OnlyFans"))
    assert not live.enabled() and not live.once_enabled() and not live.watch_enabled()
    scraper.scrapper()
    assert seen == ["prompts"]  # exactly today's OnlyFans path


# ------------------------------------------------------------------ review fixes

def one_part_recorder(save_location, chat=None, playback="https://live.example.invalid/m.m3u8?token=t",
                      variants=None, fail_first=False):
    """A recorder whose stream is live for one part, then ends."""
    calls = []
    commands = []

    async def fetch_channel():
        calls.append(1)
        if fail_first and len(calls) == 1:
            raise live.PlaylistError("channel fetch failed")
        live_now = len(calls) == (2 if fail_first else 1)
        return live_api.parse_channel(channel_response(CREATOR_A[0], playback, status=2 if live_now else 0))

    async def fetch_text(url):
        if variants is not None and "m.m3u8" in url:
            return variants
        return "#EXTM3U\n#EXTINF:2.0,\ns.ts\n"

    async def fake_ffmpeg(cmd, stop=None):
        commands.append(cmd)
        await asyncio.sleep(0.05)
        with open(cmd[-1], "wb") as f:
            f.write(b"x")
        return 0

    rec = live.LiveRecorder(stream_a(), save_location, fetch_channel, fetch_text,
                            ffmpeg_runner=fake_ffmpeg, backoff=(0, 0), chat=chat)
    return rec, commands


def test_restart_mid_stream_keeps_the_earlier_parts_in_the_sidecar(tmp_path):
    # first run records part 1; the app is then restarted while the same
    # stream is still live and the second run records part 2
    first, _ = one_part_recorder(tmp_path)
    asyncio.run(first.run())
    second, _ = one_part_recorder(tmp_path)
    sidecar = asyncio.run(second.run())

    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    part1, part2 = f"creator_a_{STAMP}_live.mp4", f"creator_a_{STAMP}_live_part2.mp4"
    assert sorted(p.name for p in folder.glob("*.mp4")) == [part1, part2]
    assert sidecar["parts"] == [part1, part2]
    on_disk = json.loads((folder / f"creator_a_{STAMP}_live.json").read_text(encoding="utf-8"))
    assert on_disk["parts"] == [part1, part2]


@pytest.mark.parametrize("other_bytes", [b"another recording", b""])
def test_a_part_taken_by_another_process_is_never_used(tmp_path, monkeypatch, other_bytes):
    # another app process creates part 1 between the free-name check and
    # ffmpeg's start; that file must not be written, listed or deleted
    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    taken = folder / f"creator_a_{STAMP}_live.mp4"
    real_next = live.next_part_number

    def racing_next(base):
        n = real_next(base)
        folder.mkdir(parents=True, exist_ok=True)
        if not taken.exists():
            taken.write_bytes(other_bytes)
        return n

    monkeypatch.setattr(live, "next_part_number", racing_next)
    rec, commands = one_part_recorder(tmp_path)
    sidecar = asyncio.run(rec.run())

    assert taken.exists() and taken.read_bytes() == other_bytes
    assert taken.name not in sidecar["parts"]
    assert sidecar["parts"] == [f"creator_a_{STAMP}_live_part2.mp4"]
    assert all(str(taken) not in c for c in commands)


def test_the_part_file_exists_before_ffmpeg_starts(tmp_path):
    seen = []
    rec, _ = one_part_recorder(tmp_path)
    inner = rec.ffmpeg_runner

    async def checking_ffmpeg(cmd, stop=None):
        seen.append(live.pathlib.Path(cmd[-1]).exists())
        return await inner(cmd, stop)

    rec.ffmpeg_runner = checking_ffmpeg
    asyncio.run(rec.run())
    assert seen == [True]


@pytest.mark.parametrize("how", ["ffmpeg_missing", "cancelled"])
def test_reserved_part_is_removed_when_nothing_was_recorded(tmp_path, how):
    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    rec, _ = one_part_recorder(tmp_path)
    started = []

    async def broken_ffmpeg(cmd, stop=None):
        started.append(live.pathlib.Path(cmd[-1]).exists())
        if how == "ffmpeg_missing":
            raise FileNotFoundError("ffmpeg")
        await asyncio.Event().wait()

    rec.ffmpeg_runner = broken_ffmpeg

    async def main():
        task = asyncio.ensure_future(rec.run())
        if how == "cancelled":
            while not started:
                await asyncio.sleep(0.01)
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(asyncio.wait_for(main(), timeout=30))
    assert started and started[0]  # a part file was reserved
    assert list(folder.glob("*.mp4")) == []


@pytest.mark.parametrize("how", ["raises", "cancelled"])
def test_a_part_with_data_is_kept_when_the_runner_fails_afterwards(tmp_path, how):
    # e.g. ffmpeg is slow to exit after a stop, the wait times out and it is
    # killed: what it already wrote must be kept and listed
    folder = tmp_path / "Fansly" / "creator_a" / "Livestreams"
    rec, _ = one_part_recorder(tmp_path)
    wrote = []

    async def ffmpeg_then_fail(cmd, stop=None):
        with open(cmd[-1], "wb") as f:
            f.write(b"video")
        wrote.append(cmd[-1])
        if how == "raises":
            raise TimeoutError("ffmpeg did not exit")
        await asyncio.Event().wait()

    rec.ffmpeg_runner = ffmpeg_then_fail

    async def main():
        task = asyncio.ensure_future(rec.run())
        if how == "cancelled":
            while not wrote:
                await asyncio.sleep(0.01)
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(asyncio.wait_for(main(), timeout=30))
    part = folder / f"creator_a_{STAMP}_live.mp4"
    assert part.read_bytes() == b"video"
    sidecar = json.loads((folder / f"creator_a_{STAMP}_live.json").read_text(encoding="utf-8"))
    assert part.name in sidecar["parts"]


def test_claim_is_released_only_once():
    # a second release would drop a claim another thread made in between
    released = []
    real_release = live.release
    stream = stream_a()

    async def main():
        stop, wake = asyncio.Event(), asyncio.Event()

        async def record(s, stop_event):
            return None

        watcher = live.LiveWatcher(None, record, interval=1000, jitter=0)
        live.release = lambda key: (released.append(key), real_release(key))
        try:
            assert watcher._start(stream, stop, wake)
            await asyncio.gather(*watcher.active.values(), return_exceptions=True)
            await asyncio.sleep(0)
        finally:
            live.release = real_release

    asyncio.run(main())
    assert released == [stream["accountId"]]


def test_one_shot_run_and_watch_thread_never_record_the_same_creator_at_once():
    stream = stream_a()
    in_thread = threading.Event()
    recorded = []

    async def watch_runner(watch, stop):
        async def record(s, stop_event):
            recorded.append("watch")
            in_thread.set()
            await stop_event.wait()

        async def fetch_online():
            return [stream]

        await live.LiveWatcher(fetch_online, record, interval=1000, jitter=0).run(stop)

    async def one_shot():
        async def record(s, stop_event):
            recorded.append("one-shot")

        async def fetch_online():
            return [stream]

        await live.LiveWatcher(fetch_online, record, once=True).run()

    thread = live.LiveThread(True, watch_runner)  # the daemon's watch thread
    thread.start()
    try:
        assert in_thread.wait(5)
        asyncio.run(asyncio.wait_for(one_shot(), timeout=5))  # the scheduled --live run
        assert recorded == ["watch"]
    finally:
        thread.stop(timeout=5)
    assert not thread.is_alive()
    # once the watch thread's recording ended, the creator can be recorded again
    asyncio.run(asyncio.wait_for(one_shot(), timeout=5))
    assert recorded == ["watch", "one-shot"]


def test_claims_are_released_when_a_recording_fails():
    async def scenario():
        async def record(s, stop_event):
            raise RuntimeError("boom")

        async def fetch_online():
            return [stream_a()]

        await live.LiveWatcher(fetch_online, record, once=True).run()

    asyncio.run(scenario())
    assert live.claim(CREATOR_A[0])
    live.release(CREATOR_A[0])


def test_daemon_live_without_actions_skips_the_action_prompt(monkeypatch, fansly_settings):
    fansly_settings(live=True)
    seen = []
    monkeypatch.setattr(settings, "get_args", lambda copy=False: SimpleNamespace(
        daemon=5.0, actions=[], scrape_paid=False))
    monkeypatch.setattr(scraper.prompts, "action_prompt", lambda: seen.append("prompt"))
    monkeypatch.setattr(scraper, "daemon_process", lambda: seen.append("daemon"))
    scraper.scrapper()
    assert seen == ["daemon"]


@pytest.fixture
def clean_patterns(monkeypatch):
    import ofscraper.utils.logs.utils.sensitive as sensitive

    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: None)


def test_playback_and_variant_tokens_are_masked_in_logs(tmp_path, clean_patterns):
    from ofscraper.utils.logs.classes.classes import SensitiveFormatter

    playback_token = "eyJhbGciOi.J+payload/part=="
    variant_token = "vt0123456789abcdef"
    master = ("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=900000\n"
              f"https://cdn.example.invalid/v/playlist.m3u8?vt={variant_token}\n")
    rec, _ = one_part_recorder(tmp_path, playback=f"https://live.example.invalid/m.m3u8?token={playback_token}",
                               variants=master)
    asyncio.run(rec.run())
    line = SensitiveFormatter()._filter(
        f"failed: https://live.example.invalid/m.m3u8?token={playback_token} "
        f"and https://cdn.example.invalid/v/playlist.m3u8?vt={variant_token}")
    assert playback_token not in line and variant_token not in line
    assert "example.invalid/m.m3u8" in line  # the rest of the line stays readable


def test_ffmpeg_error_text_is_logged_without_query_strings():
    err = "[hls @ 0x1] HTTP error 403 Forbidden for 'https://cdn.example.invalid/v/seg1.ts?vt=secret123456'"
    out = live.strip_queries(err)
    assert "secret123456" not in out
    assert "https://cdn.example.invalid/v/seg1.ts?{hidden}" in out


def test_chat_starts_on_the_next_refresh_when_the_first_channel_fetch_fails(tmp_path):
    connects = []

    async def connect():
        connects.append(1)
        return FakeSocket([])

    chat = live_chat.ChatRecorder(connect, TOKEN, ping_interval=(0.01, 0.02))
    rec, commands = one_part_recorder(tmp_path, chat=chat, fail_first=True)
    sidecar = asyncio.run(rec.run())
    assert len(commands) == 1
    assert connects == [1]
    assert sidecar["chat"] == f"creator_a_{STAMP}_live_chat.jsonl"


def test_only_https_variant_urls_reach_ffmpeg(tmp_path):
    master = ("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=900000\n"
              "file:///etc/passwd\n")
    rec, commands = one_part_recorder(tmp_path, variants=master)
    sidecar = asyncio.run(rec.run())
    assert commands == []
    assert sidecar["parts"] == []


@pytest.mark.parametrize("name", ["../escape", "a/b", "a\\b", "..", "x:y"])
def test_api_username_is_cleaned_before_it_becomes_a_folder(tmp_path, name):
    base = live.recording_base(tmp_path, name, STARTED_MS)
    livestreams = base.parent
    assert livestreams.name == "Livestreams"
    assert livestreams.parent.parent == tmp_path / "Fansly"  # one folder level, inside Fansly
    assert livestreams.parent.name not in ("", ".", "..")
    assert not set("/\\:") & set(livestreams.parent.name + base.name)
