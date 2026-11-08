"""Record Fansly livestreams to MP4 with ffmpeg.

One recording follows one creator's stream until it ends:

1. Fetch the creator's channel right before starting, for a fresh
   ``stream.playbackUrl`` (its ``?token=`` lasts only seconds).
2. Read the master playlist and pick the highest-bandwidth variant.
3. Run ffmpeg as a stream copy into fragmented MP4 (stays playable even if
   the process is stopped) until it exits.
4. If the variant playlist now ends with ``#EXT-X-ENDLIST`` or the channel is
   no longer live, stop. Otherwise the recording dropped: wait (bounded
   backoff), fetch a fresh playback URL and continue into the next part
   (``..._live_part2.mp4``). After ``max_failures`` drops in a row without
   new data, stop.

A ``.json`` sidecar next to the video lists the stream id, title, start time,
channel id and the parts. Optional chat (off by default) is written to
``..._chat.jsonl`` by ``live_chat``. Nothing here posts to Fansly.
"""

import asyncio
import datetime
import json
import logging
import pathlib
import random
import re
import threading
from urllib.parse import parse_qsl, urljoin, urlparse

from ofscraper.sites.fansly import constants
from ofscraper.utils.username_match import matches_username, username_keys

log = logging.getLogger("shared")

DEFAULT_INTERVAL = 60
DEFAULT_JITTER = 10
DEFAULT_MAX_CONCURRENT = 2
DEFAULT_MAX_FAILURES = 3
# only these URL schemes are handed to ffmpeg (a playlist entry such as
# ``file:`` would otherwise make it read a local file)
FFMPEG_SCHEMES = ("https",)


class PlaylistError(Exception):
    pass


# ------------------------------------------------------------------ who is being recorded

# One set for the whole process: the one-shot --live run and the daemon's
# watch thread each have their own LiveWatcher and event loop, and must never
# record the same creator at the same time.
_recording_lock = threading.Lock()
_recording = set()


def claim(account_id) -> bool:
    """Mark a creator as being recorded; False if someone already is."""
    with _recording_lock:
        if account_id in _recording:
            return False
        _recording.add(account_id)
        return True


def release(account_id):
    with _recording_lock:
        _recording.discard(account_id)


# ------------------------------------------------------------------ log masking

def mask_url_secrets(url):
    """Hide a playback or variant URL's query values (tokens) in the logs.

    Failed requests log their URL, and the tokens in these query strings
    grant access to the stream for a short while.
    """
    if not url:
        return
    import ofscraper.utils.logs.utils.sensitive as sensitive

    query = urlparse(url).query
    # the raw values are what a logged URL shows; the decoded ones too, in
    # case something logs them unquoted ("+" and "%2F" in a token)
    values = {piece.partition("=")[2] for piece in query.split("&")}
    values |= {value for _, value in parse_qsl(query)}
    for value in values:
        if len(value) >= 8:
            # the patterns are regexes and a token can hold "+" or "/"
            sensitive.add_sensitive_pattern(re.compile(re.escape(value)), "{hidden}")


_QUERY_IN_TEXT = re.compile(r"(\w+://[^\s?'\"]+)\?[^\s'\"]*")


def strip_queries(text: str) -> str:
    """Drop query strings from URLs in free text such as ffmpeg's errors."""
    return _QUERY_IN_TEXT.sub(r"\1?{hidden}", text or "")


# ------------------------------------------------------------------ playlists

def is_media_playlist(text: str) -> bool:
    return "#EXTINF" in text or "#EXT-X-TARGETDURATION" in text


def has_endlist(text: str) -> bool:
    return "#EXT-X-ENDLIST" in (text or "")


def parse_master(text: str, base_url: str) -> list:
    """Variants of a master playlist: bandwidth, width, height and absolute URI."""
    out = []
    lines = [line.strip() for line in (text or "").splitlines()]
    for i, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = line.split(":", 1)[1]
        bw = re.search(r"(?:^|,)BANDWIDTH=(\d+)", attrs)
        res = re.search(r"RESOLUTION=(\d+)x(\d+)", attrs)
        uri = next((u for u in lines[i + 1:] if u and not u.startswith("#")), None)
        if not uri:
            continue
        out.append(
            {
                "bandwidth": int(bw.group(1)) if bw else 0,
                "width": int(res.group(1)) if res else 0,
                "height": int(res.group(2)) if res else 0,
                "uri": urljoin(base_url, uri),
            }
        )
    return out


def pick_variant(variants: list):
    """Highest bandwidth; on a tie the larger picture."""
    if not variants:
        return None
    return max(variants, key=lambda v: (v["bandwidth"], v["width"] * v["height"]))


# ------------------------------------------------------------------ paths and sidecar

def utc_start(started_at) -> datetime.datetime:
    """Stream start in UTC from milliseconds or seconds; now when unknown."""
    if started_at:
        try:
            value = float(started_at)
            value = value / 1000 if value > 1e10 else value
            return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    return datetime.datetime.now(tz=datetime.timezone.utc)


def folder_name(username) -> str:
    """The API username, safe as one folder or file name component."""
    from ofscraper.classes.of.base import base

    # the app's own filename cleanup; it leaves backslashes and dots alone
    name = base().file_cleanup(username).replace("\\", "").strip(" .")
    return name or "unknown"


def recording_base(save_location, username, started_at) -> pathlib.Path:
    """``{save_location}/Fansly/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live``"""
    stamp = utc_start(started_at).strftime("%Y%m%d_%H%M%S")
    username = folder_name(username)
    folder = pathlib.Path(save_location) / "Fansly" / username / "Livestreams"
    return folder / f"{username}_{stamp}_live"


def part_path(base: pathlib.Path, n: int) -> pathlib.Path:
    return base.with_name(f"{base.name}.mp4" if n == 1 else f"{base.name}_part{n}.mp4")


def next_part_number(base: pathlib.Path) -> int:
    n = 1
    while part_path(base, n).exists():
        n += 1
    return n


def reserve_part(base: pathlib.Path) -> pathlib.Path:
    """Create the next free part file exclusively and return it.

    Only a file this recorder created is ever handed to ffmpeg, counted as a
    part or deleted, even when another process records the same stream.
    """
    base.parent.mkdir(parents=True, exist_ok=True)
    n = next_part_number(base)
    while True:
        path = part_path(base, n)
        try:
            with open(path, "x"):
                return path
        except FileExistsError:
            n += 1


def sidecar_path(base: pathlib.Path) -> pathlib.Path:
    return base.with_name(f"{base.name}.json")


def chat_path(base: pathlib.Path) -> pathlib.Path:
    return base.with_name(f"{base.name}_chat.jsonl")


# ------------------------------------------------------------------ ffmpeg

def ffmpeg_command(ffmpeg: str, url: str, out: pathlib.Path, user_agent: str = "") -> list:
    headers = f"Origin: {constants.ORIGIN}\r\nReferer: {constants.REFERER}\r\n"
    # -y: ``out`` is the empty file reserve_part() created for this recording
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if user_agent:
        cmd += ["-user_agent", user_agent]
    cmd += [
        "-headers", headers,
        "-live_start_index", "0",
        "-i", url,
        "-map", "0:v?", "-map", "0:a?",
        "-c", "copy",
        # HLS transport streams carry ADTS AAC, which MP4 can't hold as is
        "-bsf:a", "aac_adtstoasc",
        "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
        str(out),
    ]
    return cmd


async def run_ffmpeg(cmd: list, stop: asyncio.Event = None) -> int:
    """Run ffmpeg until it exits; on ``stop`` it is asked to finish cleanly."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    waiter = asyncio.ensure_future(proc.communicate())
    stopper = asyncio.ensure_future(stop.wait()) if stop else None
    try:
        done, _ = await asyncio.wait(
            [waiter] + ([stopper] if stopper else []), return_when=asyncio.FIRST_COMPLETED
        )
        if waiter not in done:
            proc.terminate()
            await asyncio.wait_for(asyncio.shield(waiter), timeout=15)
        _, err = waiter.result()
        if proc.returncode and err:
            log.debug(f"ffmpeg live: {strip_queries(err.decode(errors='replace'))[-500:]}")
        return proc.returncode
    finally:
        if stopper:
            stopper.cancel()
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


# ------------------------------------------------------------------ one recording

class LiveRecorder:
    """Record one creator's live stream into numbered parts plus a sidecar.

    ``fetch_channel()`` returns a parsed channel (``live``, ``playbackUrl``,
    ``stream``...), ``fetch_text(url)`` returns a playlist's text or raises,
    ``ffmpeg_runner(cmd, stop)`` runs ffmpeg. All three are injectable so the
    recorder can be tested without Fansly.
    """

    def __init__(self, stream: dict, save_location, fetch_channel, fetch_text,
                 ffmpeg="ffmpeg", user_agent="", ffmpeg_runner=None,
                 max_failures=DEFAULT_MAX_FAILURES, backoff=(2, 30), chat=None,
                 schemes=FFMPEG_SCHEMES):
        self.stream = dict(stream)
        self.username = stream["username"]
        self.save_location = save_location
        self.fetch_channel = fetch_channel
        self.fetch_text = fetch_text
        self.ffmpeg = ffmpeg
        self.user_agent = user_agent
        self.ffmpeg_runner = ffmpeg_runner or run_ffmpeg
        self.max_failures = max_failures
        self.backoff = backoff
        self.chat = chat
        self.schemes = tuple(schemes)
        self.parts = []
        # parts and chat file listed by an earlier run of the same stream
        self.earlier = {"parts": [], "chat": None}
        self.base = None
        self.end_reason = None
        self.sidecar = {}

    def _backoff_delay(self, failures: int) -> float:
        first, cap = self.backoff
        return min(first * (2 ** max(failures - 1, 0)), cap)

    async def _resolve_variant(self, playback_url: str) -> str:
        text = await self.fetch_text(playback_url)
        if is_media_playlist(text):
            return playback_url
        variant = pick_variant(parse_master(text, playback_url))
        if not variant:
            raise PlaylistError("the master playlist lists no variants")
        return variant["uri"]

    def _read_earlier_sidecar(self):
        """A restart while the same stream is live continues its recording:
        keep the parts the earlier run listed."""
        path = sidecar_path(self.base)
        if not path.exists():
            return
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.debug(f"{self.username}: could not read the earlier sidecar: {e}")
            return
        if not isinstance(old, dict):
            return
        parts = old.get("parts")
        if isinstance(parts, list):
            self.earlier["parts"] = [p for p in parts if isinstance(p, str)]
        if isinstance(old.get("chat"), str):
            self.earlier["chat"] = old["chat"]

    def _write_sidecar(self):
        stream = self.stream
        parts = list(self.earlier["parts"])
        parts += [p.name for p in self.parts if p.name not in parts]
        self.sidecar = {
            "site": "fansly",
            "accountId": stream.get("accountId"),
            "username": self.username,
            "streamId": stream.get("streamId"),
            "channelId": stream.get("channelId"),
            "title": stream.get("title"),
            "startedAt": utc_start(stream.get("startedAt")).isoformat(),
            "parts": parts,
            "chat": chat_path(self.base).name if self.chat else self.earlier["chat"],
            "endReason": self.end_reason,
        }
        path = sidecar_path(self.base)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

    def _update_stream(self, channel: dict):
        s = channel.get("stream") or {}
        for key, value in (("streamId", s.get("id")), ("channelId", channel.get("id") or s.get("channelId")),
                           ("title", s.get("title")), ("startedAt", s.get("startedAt"))):
            if value and not self.stream.get(key):
                self.stream[key] = value

    async def run(self, stop: asyncio.Event = None) -> dict:
        stop = stop or asyncio.Event()
        failures = 0
        chat_task = None
        try:
            while not stop.is_set():
                try:
                    channel = await self.fetch_channel()
                except Exception as e:
                    log.debug(f"{self.username}: channel fetch failed: {e}")
                    channel = None
                if channel is not None and not channel.get("live"):
                    self.end_reason = self.end_reason or "not live"
                    break
                if channel is not None:
                    self._update_stream(channel)
                    mask_url_secrets(channel.get("playbackUrl"))
                if self.base is None:
                    self.base = recording_base(self.save_location, self.username,
                                               self.stream.get("startedAt"))
                    self.base.parent.mkdir(parents=True, exist_ok=True)
                    self._read_earlier_sidecar()
                # chat starts with the first channel that came back, so a
                # failed first fetch only delays it to the next refresh
                if self.chat and channel and chat_task is None:
                    chat_task = asyncio.ensure_future(
                        self.chat.run(channel, chat_path(self.base), stop))
                ended, produced = await self._record_part(channel, stop)
                if ended:
                    self.end_reason = "stream ended"
                    break
                failures = 0 if produced else failures + 1
                if failures >= self.max_failures:
                    self.end_reason = f"stopped after {failures} failed attempts"
                    log.info(f"{self.username}: livestream recording {self.end_reason}")
                    break
                delay = self._backoff_delay(failures or 1)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
            if stop.is_set() and not self.end_reason:
                self.end_reason = "stopped"
        finally:
            if chat_task:
                chat_task.cancel()
                await asyncio.gather(chat_task, return_exceptions=True)
            if self.base is not None:
                self._write_sidecar()
        return self.sidecar

    async def _record_part(self, channel, stop):
        """Record one part. Returns (stream ended, new data written)."""
        if channel is None or not channel.get("playbackUrl"):
            return False, False
        try:
            variant = await self._resolve_variant(channel["playbackUrl"])
        except Exception as e:
            log.debug(f"{self.username}: playlist failed: {e}")
            return False, False
        mask_url_secrets(variant)
        scheme = urlparse(variant).scheme.lower()
        if scheme not in self.schemes:
            log.info(f"{self.username}: skipping a variant URL with scheme {scheme or 'none'!r}")
            return False, False
        out = reserve_part(self.base)
        log.info(f"{self.username}: recording livestream to {out.name}")
        try:
            await self.ffmpeg_runner(
                ffmpeg_command(self.ffmpeg, variant, out, self.user_agent), stop)
        finally:
            # decided from the file, so a part ffmpeg wrote is kept and listed
            # even when the runner raised or was cancelled afterwards; an
            # empty reserved file (ffmpeg wrote nothing) is removed
            produced = out.exists() and out.stat().st_size > 0
            if produced:
                self.parts.append(out)
                self._write_sidecar()
            else:
                out.unlink(missing_ok=True)
        if stop.is_set():
            return False, produced
        try:
            ended = has_endlist(await self.fetch_text(variant))
        except Exception as e:
            log.debug(f"{self.username}: playlist re-check failed: {e}")
            ended = False
        return ended, produced


# ------------------------------------------------------------------ several creators

def select_streams(online: list, usernames=None, excluded=None) -> list:
    """Live streams of the selected creators (all followed when none or ALL)."""
    wanted = username_keys(usernames)
    skip = username_keys(excluded)
    out = [s for s in online if not matches_username(s.get("username"), skip)]
    if not wanted or "all" in wanted:
        return out
    return [s for s in out if matches_username(s.get("username"), wanted)]


class LiveWatcher:
    """Poll who is live and keep at most ``max_concurrent`` recordings running.

    ``fetch_online()`` returns the selected live streams; ``record(stream,
    stop)`` records one. Creators already being recorded aren't started twice;
    when a recording ends the next waiting creator starts straight away.
    """

    def __init__(self, fetch_online, record, max_concurrent=DEFAULT_MAX_CONCURRENT,
                 interval=DEFAULT_INTERVAL, jitter=DEFAULT_JITTER, once=False):
        self.fetch_online = fetch_online
        self.record = record
        self.max_concurrent = max(1, int(max_concurrent or 1))
        self.interval = interval
        self.jitter = jitter
        self.once = once
        self.active = {}
        self.max_seen = 0

    def _start(self, stream, stop, wake) -> bool:
        key = stream["accountId"]
        if not claim(key):
            # recorded by another watcher in this process (the one-shot
            # --live run or the daemon's watch thread); the next poll retries
            log.debug(f"{stream.get('username')}: already being recorded")
            return False

        async def runner():
            try:
                await self.record(stream, stop)
            except Exception as e:
                log.info(f"{stream.get('username')}: livestream recording failed: {e}")
            finally:
                self.active.pop(key, None)
                wake.set()

        task = asyncio.ensure_future(runner())
        # the only release: it also runs when the task is cancelled before it
        # ever ran. Releasing in runner() as well could drop a claim another
        # thread made in between.
        task.add_done_callback(lambda _: release(key))
        self.active[key] = task
        self.max_seen = max(self.max_seen, len(self.active))
        return True

    async def run(self, stop: asyncio.Event = None):
        """Watch until ``stop``; with ``once`` only who is live now, then return."""
        stop = stop or asyncio.Event()
        wake = asyncio.Event()
        queue = []
        poll = True
        while not stop.is_set():
            wake.clear()
            if poll:
                try:
                    queue = list(await self.fetch_online())
                except Exception as e:
                    log.debug(f"live check failed: {e}")
            queue = [s for s in queue if s["accountId"] not in self.active]
            while queue and len(self.active) < self.max_concurrent:
                self._start(queue.pop(0), stop, wake)
            if self.once:
                if not queue and not self.active:
                    break
                poll = False
                await _either(wake, stop)
                continue
            timeout = self.interval + random.uniform(0, self.jitter)
            try:
                await asyncio.wait_for(_either(wake, stop), timeout=timeout)
                # a recording ended: start the next waiting creator now,
                # the next poll still happens on the interval
                poll = not wake.is_set()
            except asyncio.TimeoutError:
                poll = True
        if self.active:
            await asyncio.gather(*self.active.values(), return_exceptions=True)


async def _either(a: asyncio.Event, b: asyncio.Event):
    tasks = [asyncio.ensure_future(a.wait()), asyncio.ensure_future(b.wait())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# ------------------------------------------------------------------ app glue

def options(s=None) -> dict:
    """Livestream options from the merged settings (all default to off/brief values)."""
    import ofscraper.utils.settings as settings

    s = s or settings.get_settings()
    return {
        "once": bool(getattr(s, "live", False)),
        "watch": bool(getattr(s, "live_watch", False)),
        "interval": getattr(s, "live_interval", None) or DEFAULT_INTERVAL,
        "max_concurrent": getattr(s, "live_max", None) or DEFAULT_MAX_CONCURRENT,
        "chat": bool(getattr(s, "live_chat", False)),
        "usernames": getattr(s, "usernames", None),
        "excluded": getattr(s, "excluded_username", None),
    }


def requested(s=None) -> bool:
    opts = options(s)
    return opts["once"] or opts["watch"]


_warned = False


def enabled(s=None) -> bool:
    """Livestream options apply to Fansly profiles only; OnlyFans ignores them."""
    global _warned
    import ofscraper.sites as sites

    if not requested(s):
        return False
    if not sites.is_fansly():
        if not _warned:
            log.warning("--live/--live-watch only apply to Fansly profiles; ignoring them")
            _warned = True
        return False
    return True


def once_enabled(s=None) -> bool:
    return enabled(s) and options(s)["once"]


def watch_enabled(s=None) -> bool:
    return enabled(s) and options(s)["watch"]


class LiveThread(threading.Thread):
    """Runs ``run()`` on its own event loop so it can be stopped cleanly."""

    def __init__(self, watch: bool, runner=None):
        super().__init__(daemon=True, name="fansly-live")
        self.watch = watch
        self.runner = runner or run
        self.loop = None
        self.stop_event = None
        self.ready = threading.Event()

    def run(self):
        loop = asyncio.new_event_loop()
        self.loop = loop
        try:
            asyncio.set_event_loop(loop)
            self.stop_event = asyncio.Event()
            self.ready.set()
            loop.run_until_complete(self.runner(self.watch, self.stop_event))
        except Exception as e:
            log.info(f"livestream recording stopped: {e}")
            log.debug("", exc_info=True)
        finally:
            self.ready.set()
            loop.close()

    def stop(self, timeout=30):
        self.ready.wait(5)
        loop = self.loop
        if loop is not None and self.stop_event is not None:
            try:
                loop.call_soon_threadsafe(self.stop_event.set)
            except RuntimeError:
                pass  # loop already closed
        self.join(timeout)


def run_blocking(watch: bool, runner=None):
    """Record in the foreground; Ctrl+C stops the recordings cleanly first."""
    thread = LiveThread(watch, runner)
    thread.start()
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        log.info("stopping livestream recording")
        thread.stop()
        raise


def start_watch_thread(runner=None) -> LiveThread:
    """Daemon mode: watch for livestreams beside the scheduled scrapes."""
    thread = LiveThread(True, runner)
    thread.start()
    return thread


async def run(watch: bool = False, stop: asyncio.Event = None):
    """Record the selected creators who are live: once, or watching until stopped."""
    import ofscraper.managers.manager as manager
    import ofscraper.utils.paths.common as common_paths
    import ofscraper.utils.system.ffmpeg as ffmpeg_finder
    from ofscraper.managers.sessionmanager.sessionmanager import HEADERS
    from ofscraper.sites.fansly import auth as fansly_auth
    from ofscraper.sites.fansly import live_api, live_chat

    opts = options()
    auth = fansly_auth.read_auth()
    save_location = common_paths.get_save_location()
    ffmpeg = ffmpeg_finder.get_ffmpeg()

    # playlists get one attempt each: a 403 means "fetch a fresh URL", not "retry"
    async with manager.Manager.session.aget_ofsession() as c, \
            manager.Manager.session.aget_ofsession(retries=1) as playlists:

        async def fetch_online():
            online = await live_api.get_online_streams(c)
            return select_streams(online, opts["usernames"], opts["excluded"])

        async def fetch_text(url):
            # CDN playlist: session routing gives it browser headers only
            async with playlists.requests_async(url=url, actions=[HEADERS], exceptions=[]) as r:
                if r.status_code == 404:
                    raise PlaylistError("playlist not found")
                return await r.text_()

        async def record(stream, stop_event):
            async def fetch_channel():
                return await live_api.get_channel(c, stream["accountId"])

            chat = None
            if opts["chat"]:
                chat = live_chat.ChatRecorder(
                    live_chat.aiohttp_connect(auth.get("user_agent")),
                    auth.get("authorization_token"),
                )
            await LiveRecorder(
                stream, save_location, fetch_channel, fetch_text,
                ffmpeg=ffmpeg, user_agent=auth.get("user_agent") or "", chat=chat,
            ).run(stop_event)

        watcher = LiveWatcher(
            fetch_online, record,
            max_concurrent=opts["max_concurrent"],
            interval=opts["interval"],
            once=not watch,
        )
        await watcher.run(stop)
