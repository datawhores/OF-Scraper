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
import json
import logging
import os
import pathlib
import re
import threading  # noqa: F401  (accessed by tests as live.threading)
from urllib.parse import parse_qsl, urljoin, urlparse

import ofscraper.utils.events as events
import ofscraper.utils.live.runtime as runtime
from ofscraper.sites.fansly import constants
from ofscraper.utils.live.runtime import (
    _RECORDING as _RECORDING,
)
from ofscraper.utils.live.runtime import (
    _RECORDING_LOCK as _RECORDING_LOCK,
)
from ofscraper.utils.live.runtime import (
    DEFAULT_INTERVAL as DEFAULT_INTERVAL,
)
from ofscraper.utils.live.runtime import (
    DEFAULT_JITTER as DEFAULT_JITTER,
)
from ofscraper.utils.live.runtime import (
    DEFAULT_MAX_CONCURRENT as DEFAULT_MAX_CONCURRENT,
)
from ofscraper.utils.live.runtime import (
    DEFAULT_MAX_FAILURES as DEFAULT_MAX_FAILURES,
)
from ofscraper.utils.live.runtime import (
    REFRESH_USERS_SECONDS as REFRESH_USERS_SECONDS,
)
from ofscraper.utils.live.runtime import (
    LiveThread as LiveThread,
)
from ofscraper.utils.live.runtime import (
    LiveWatcher as LiveWatcher,
)
from ofscraper.utils.live.runtime import (
    PollStateLogger as PollStateLogger,
)
from ofscraper.utils.live.runtime import (
    _either as _either,
)
from ofscraper.utils.live.runtime import (
    _float_env as _float_env,
)
from ofscraper.utils.live.runtime import (
    _int_env as _int_env,
)
from ofscraper.utils.live.runtime import (
    _resolve_live_jitter as _resolve_live_jitter,
)
from ofscraper.utils.live.runtime import (
    claim as claim,
)
from ofscraper.utils.live.runtime import (
    count_misses as count_misses,
)
from ofscraper.utils.live.runtime import (
    enabled as enabled,
)
from ofscraper.utils.live.runtime import (
    folder_name as folder_name,
)
from ofscraper.utils.live.runtime import (
    has_custom_user_filters as has_custom_user_filters,
)
from ofscraper.utils.live.runtime import (
    lookup_due as lookup_due,
)
from ofscraper.utils.live.runtime import (
    once_enabled as once_enabled,
)
from ofscraper.utils.live.runtime import (
    options as options,
)
from ofscraper.utils.live.runtime import (
    refresh_due as refresh_due,
)
from ofscraper.utils.live.runtime import (
    release as release,
)
from ofscraper.utils.live.runtime import (
    requested as requested,
)
from ofscraper.utils.live.runtime import (
    select_streams as select_streams,
)
from ofscraper.utils.live.runtime import (
    tui_enabled as tui_enabled,
)
from ofscraper.utils.live.runtime import (
    utc_start as utc_start,
)
from ofscraper.utils.live.runtime import (
    wants_all_usernames as wants_all_usernames,
)
from ofscraper.utils.live.runtime import (
    warn_streak as warn_streak,
)
from ofscraper.utils.live.runtime import (
    watch_enabled as watch_enabled,
)
from ofscraper.utils.username_match import matches_account, username_keys

log = logging.getLogger("shared")

# only these URL schemes are handed to ffmpeg (a playlist entry such as
# ``file:`` would otherwise make it read a local file)
FFMPEG_SCHEMES = ("https",)

_recording_lock = _RECORDING_LOCK
_recording = _RECORDING


class PlaylistError(Exception):
    pass


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
# the login in a link (http://user:password@host), as an OFSC_PROXY has it;
# it ends at the last "@" before the host, so a raw "@" in the password is kept in
_LOGIN_IN_TEXT = re.compile(r"([a-zA-Z][\w+.-]*://)[^\s/'\"]+@")


def strip_queries(text: str) -> str:
    """Drop query strings, and logins such as a proxy's, from URLs in free
    text such as ffmpeg's errors."""
    text = _LOGIN_IN_TEXT.sub(r"\1{hidden}@", text or "")
    return _QUERY_IN_TEXT.sub(r"\1?{hidden}", text)


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

def recording_base(save_location, username, started_at, *, model_id=None) -> pathlib.Path:
    """``{save_location}/Fansly/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live``"""
    import ofscraper.classes.placeholder as placeholder

    path = placeholder.live_recording_path(
        save_location, folder_name(username), utc_start(started_at),
        site_name="Fansly", ext="mp4", model_id=model_id, reserve_suffix=_CHAT_SUFFIX,
    )
    return path.with_suffix("")


_CHAT_SUFFIX = "_chat.jsonl"


def part_path(base: pathlib.Path, n: int, *, started_at=None) -> pathlib.Path:
    import ofscraper.classes.placeholder as placeholder

    suffix = ".mp4" if n == 1 else f"_part{n}.mp4"
    if len(suffix) > len(_CHAT_SUFFIX):
        base = placeholder.fit_with_suffix(base, suffix, started_at)
    return base.with_name(f"{base.name}{suffix}")


def next_part_number(base: pathlib.Path, *, started_at=None) -> int:
    n = 1
    while part_path(base, n, started_at=started_at).exists():
        n += 1
    return n


def reserve_part(base: pathlib.Path, *, started_at=None) -> pathlib.Path:
    """Create the next free part file exclusively and return it.

    Only a file this recorder created is ever handed to ffmpeg, counted as a
    part or deleted, even when another process records the same stream.
    """
    base.parent.mkdir(parents=True, exist_ok=True)
    n = next_part_number(base, started_at=started_at)
    while True:
        path = part_path(base, n, started_at=started_at)
        try:
            with open(path, "x"):
                return path
        except FileExistsError:
            n += 1


def sidecar_path(base: pathlib.Path) -> pathlib.Path:
    return base.with_name(f"{base.name}.json")


def chat_path(base: pathlib.Path) -> pathlib.Path:
    return base.with_name(f"{base.name}{_CHAT_SUFFIX}")


# ------------------------------------------------------------------ ffmpeg

def ffmpeg_command(ffmpeg: str, url: str, out: pathlib.Path, user_agent: str = "") -> list:
    headers = f"Origin: {constants.ORIGIN}\r\nReferer: {constants.REFERER}\r\n"
    # -y: ``out`` is the empty file reserve_part() created for this recording
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
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


def ffmpeg_can_use(proxy: str) -> bool:
    """Whether ffmpeg sends its requests through this proxy. It only takes a
    lower-case http:// address with a host, and connects directly otherwise."""
    if not proxy.startswith("http://"):
        return False
    try:
        return bool(urlparse(proxy).hostname)
    except ValueError:
        return False


def ffmpeg_env(proxy: str) -> dict:
    """ffmpeg's environment with OFSC_PROXY as its proxy.

    ffmpeg reads ``http_proxy`` for every playlist reload and segment request,
    https ones included. It goes in the environment rather than -http_proxy so
    the proxy's login isn't in the command line, which other users can read.
    ``no_proxy`` is dropped: OFSC_PROXY is for every request. A proxy ffmpeg
    would ignore is refused rather than connecting directly.
    """
    if not ffmpeg_can_use(proxy):
        raise ValueError("ffmpeg can only use an http:// proxy")
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy", "http_proxy")}
    env["http_proxy"] = proxy
    return env


async def run_ffmpeg(cmd: list, stop: asyncio.Event = None, proxy: str = None) -> int:
    """Run ffmpeg until it exits; on ``stop`` it is asked to finish cleanly."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        env=ffmpeg_env(proxy) if proxy else None,
    )
    waiter = asyncio.ensure_future(proc.communicate())
    stopper = asyncio.ensure_future(stop.wait()) if stop else None
    try:
        done, _ = await asyncio.wait(
            [waiter] + ([stopper] if stopper else []), return_when=asyncio.FIRST_COMPLETED
        )
        if waiter not in done:
            try:
                if proc.stdin and not getattr(proc.stdin, "is_closing", lambda: False)():
                    proc.stdin.write(b"q\n")
                    await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError, RuntimeError):
                pass  # ffmpeg exited while the stop request was being sent
            try:
                await asyncio.wait_for(asyncio.shield(waiter), timeout=15)
            except asyncio.TimeoutError:
                proc.kill()
                await waiter
        _, err = waiter.result()
        if proc.returncode and err:
            log.debug(f"ffmpeg live: {strip_queries(err.decode(errors='replace'))[-500:]}")
        return proc.returncode
    finally:
        if stopper:
            stopper.cancel()
            await asyncio.gather(stopper, return_exceptions=True)
        if proc.returncode is None:
            proc.kill()
        if waiter.cancelled():
            await proc.wait()
        else:
            await waiter


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
                 schemes=FFMPEG_SCHEMES, proxy=None):
        self.stream = dict(stream)
        self.username = stream["username"]
        self.save_location = save_location
        self.fetch_channel = fetch_channel
        self.fetch_text = fetch_text
        self.ffmpeg = ffmpeg
        self.user_agent = user_agent
        self.proxy = proxy
        self.ffmpeg_runner = ffmpeg_runner or run_ffmpeg
        self.max_failures = max_failures
        self.backoff = backoff
        self.chat = chat
        self.schemes = tuple(schemes)
        self.parts = []
        # parts and chat file listed by an earlier run of the same stream
        self.earlier = {"parts": [], "chat": None}
        self.base = None
        self.started_at = None
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
        account_id = self.stream.get("accountId")
        events.emit_sync(
            "live_stream",
            site="fansly",
            account_id=account_id,
            username=self.username,
            status="joining",
            title=self.stream.get("title"),
            started_at=self.stream.get("startedAt"),
            reason="Checking stream channel...",
        )
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
                    self.started_at = utc_start(self.stream.get("startedAt"))
                    self.base = recording_base(self.save_location, self.username,
                                               self.started_at,
                                               model_id=self.stream.get("accountId"))
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
                events.emit_sync(
                    "live_stream",
                    site="fansly",
                    account_id=account_id,
                    username=self.username,
                    status="retrying",
                    title=self.stream.get("title"),
                    reason=f"Stream dropped; retry in {delay:.0f}s ({failures}/{self.max_failures})",
                )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
            if stop.is_set() and not self.end_reason:
                self.end_reason = "stopped"
        finally:
            if stop.is_set() and not self.end_reason:
                self.end_reason = "stopped"
            if chat_task:
                chat_task.cancel()
                await asyncio.gather(chat_task, return_exceptions=True)
            if self.base is not None:
                self._write_sidecar()
            has_parts = bool(self.parts or self.earlier["parts"])
            if stop.is_set() or self.end_reason == "stopped":
                final_status = "stopped"
            elif not has_parts and failures >= self.max_failures:
                final_status = "failed"
            else:
                final_status = "ended"
            events.emit_sync(
                "live_stream",
                site="fansly",
                account_id=account_id,
                username=self.username,
                status=final_status,
                part_path=self.parts[-1] if self.parts else None,
                part_num=len(self.earlier["parts"]) + len(self.parts),
                reason=self.end_reason or "ended",
            )
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
        out = reserve_part(self.base, started_at=self.started_at)
        log.info(f"{self.username}: recording livestream to {out.name}")
        events.emit_sync(
            "live_stream",
            site="fansly",
            account_id=self.stream.get("accountId"),
            username=self.username,
            status="recording",
            title=self.stream.get("title"),
            started_at=self.stream.get("startedAt"),
            part_path=out,
            part_num=len(self.earlier["parts"]) + len(self.parts) + 1,
            reason=out.name,
        )
        try:
            await self.ffmpeg_runner(
                ffmpeg_command(self.ffmpeg, variant, out, self.user_agent), stop,
                **({"proxy": self.proxy} if self.proxy else {}))
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


# ------------------------------------------------------------------ app glue

def run_blocking(watch: bool, runner=None, menu=False):
    """Record in the foreground; Ctrl+C stops the recordings cleanly first."""
    return runtime.run_blocking(watch, runner=runner, menu=menu, thread_cls=LiveThread)


def start_watch_thread(runner=None) -> LiveThread:
    """Daemon mode: watch for livestreams beside the scheduled scrapes."""
    return runtime.start_watch_thread(runner=runner, thread_cls=LiveThread)


async def run(watch: bool = False, stop: asyncio.Event = None):
    """Record the selected creators who are live: once, or watching until stopped."""
    import ofscraper.sites as sites

    if not sites.is_fansly():
        from ofscraper.sites.onlyfans import live as onlyfans_live

        return await onlyfans_live.run(watch, stop)

    import ofscraper.managers.manager as manager
    import ofscraper.utils.of_env.of_env as of_env
    import ofscraper.utils.paths.common as common_paths
    import ofscraper.utils.system.ffmpeg as ffmpeg_finder
    from ofscraper.classes.of.models import Model
    from ofscraper.managers.model import ModelManager
    from ofscraper.managers.sessionmanager.sessionmanager import HEADERS
    from ofscraper.sites.fansly import api as fansly_api
    from ofscraper.sites.fansly import auth as fansly_auth
    from ofscraper.sites.fansly import live_api, live_chat
    from ofscraper.sites.fansly import scrape as fansly_scrape

    opts = options()
    # Fansly lists aren't read: --user-list / --black-list choose nobody here
    opts["has_filters"] = ModelManager.has_active_filters(lists=False)
    if ModelManager.has_list_filters():
        log.warning("--user-list and --black-list don't apply to Fansly livestreams; creators on those lists are still recorded")
    auth = fansly_auth.read_auth()
    save_location = common_paths.get_save_location()
    ffmpeg = ffmpeg_finder.get_ffmpeg()
    proxy = of_env.getattr("PROXY") or None
    if proxy and not ffmpeg_can_use(proxy):
        # ffmpeg would connect directly, so nothing is recorded
        log.error(
            "Not recording Fansly livestreams: OFSC_PROXY is set, but ffmpeg "
            "can only use an http:// proxy (http://host:port or "
            "http://user:password@host:port) and would connect without it. "
            "Set OFSC_PROXY to an http:// proxy, or unset it to record "
            "without a proxy."
        )
        return

    if watch:
        log.info(
            f"Watching for Fansly livestreams (polling every {opts['interval']}s, "
            f"up to {opts['max_concurrent']} concurrent)..."
        )
    else:
        log.info("Checking for active Fansly livestreams...")

    # playlists get one attempt each: a 403 means "fetch a fresh URL", not "retry"
    async with manager.Manager.session.aget_ofsession() as c, \
            manager.Manager.session.aget_ofsession(retries=1) as playlists:
        log_poll_state = PollStateLogger("Fansly", watch)
        announced_no_targets = False
        streaks = {}
        lookups = {"poll": 0, "misses": {}}
        resolved_cache = {}
        unfollowed_cache = {}
        filtered_cache = {}
        following_set = None

        async def _get_following_set():
            nonlocal following_set
            if following_set is None:
                import ofscraper.utils.me as me_util

                try:
                    following_set = {
                        str(fid)
                        for fid in await fansly_api.following_ids(c, me_util.get_id())
                    }
                except Exception as e:
                    log.debug(f"Fansly: could not fetch following list for live fallback: {e}")
                    following_set = None
            return following_set

        async def _resolve_fansly_targets(names, unfollowed_only: bool = False):
            # a name the lookup didn't return isn't cached: it is asked again,
            # less often once it keeps missing
            unresolved = [
                u for u in names
                if u and str(u).lower() not in resolved_cache
                and lookup_due(lookups["misses"], str(u).lower(), lookups["poll"])
            ]
            if unresolved:
                models = [
                    Model(m)
                    for m in await fansly_scrape.get_models(unresolved, c=c)
                ]
                returned = {k for m in models for k in (m.name.lower(), str(m.id))}
                if opts["has_filters"] and models:
                    mm = getattr(manager.Manager, "model_manager", None) or ModelManager()
                    models = mm.filter_models(models)
                by_key = {}
                for m in models:
                    target = {"accountId": str(m.id), "username": m.name}
                    for key in {m.name.lower(), str(m.id)}:
                        by_key.setdefault(key, []).append(target)
                keys = [str(u).lower() for u in unresolved]
                for key in keys:
                    if key in returned:
                        resolved_cache[key] = by_key.get(key, [])
                count_misses(lookups["misses"], keys, [k for k in keys if k not in returned])

            if unfollowed_only:
                pending = [
                    u for u in names
                    if u and str(u).lower() not in unfollowed_cache and str(u).lower() in resolved_cache
                ]
                followed = await _get_following_set() if pending else None
                # without the following list this poll checks them all, and
                # the list is asked for again next poll
                if followed is not None:
                    for u in pending:
                        key = str(u).lower()
                        unfollowed_cache[key] = [
                            target for target in resolved_cache.get(key, [])
                            if target["accountId"] not in followed
                        ]

            out, seen = [], set()
            for u in names:
                key = str(u).lower() if u else None
                if unfollowed_only and key in unfollowed_cache:
                    targets = unfollowed_cache[key]
                else:
                    targets = resolved_cache.get(key, [])
                for target in targets:
                    if target["accountId"] not in seen:
                        seen.add(target["accountId"])
                        out.append(target)
            return out

        async def _streams_for_targets(targets):
            if not targets:
                return []
            sem = asyncio.Semaphore(opts["check_concurrency"])

            async def check_one(target):
                async with sem:
                    channel = await live_api.get_channel(c, target["accountId"])
                if channel.get("live"):
                    stream = channel.get("stream") or {}
                    return {
                        "accountId": str(target["accountId"]),
                        "username": target["username"],
                        "streamId": stream.get("id"),
                        "channelId": channel.get("id") or stream.get("channelId"),
                        "title": stream.get("title"),
                        "startedAt": stream.get("startedAt"),
                        "status": channel.get("status"),
                    }
                return None

            results = await asyncio.gather(
                *(check_one(t) for t in targets),
                return_exceptions=True,
            )
            # a failed check skips that creator only, not the creators already
            # found live; it warns once until the checks work again
            failed = [(t, r) for t, r in zip(targets, results, strict=True) if isinstance(r, Exception)]
            for target, error in failed:
                log.debug(f"Fansly: live check for {target['username']} failed: {error}")
            warn_streak(streaks, "checks", failed and (
                f"Fansly: live check failed for {len(failed)} creator(s): {failed[0][1]}"
            ))
            return [r for r in results if isinstance(r, dict)]

        async def fetch_online():
            nonlocal announced_no_targets, following_set
            lookups["poll"] += 1
            if opts["refresh_users"] and refresh_due(lookups):
                resolved_cache.clear()
                unfollowed_cache.clear()
                filtered_cache.clear()
                following_set = None
            include_following, extra_names, active_usernames, excluded = runtime.LiveWatcher.effective_scope(
                watcher, opts
            )
            search_mode = opts["username_search"]

            try:
                if not include_following and not extra_names:
                    events.emit_sync("live_poll", state="targets", site="fansly", targets=[])
                    warn_streak(streaks, "poll")
                    log_poll_state([])
                    return []

                # Individual search (-fi) with explicit usernames only (Following OFF)
                if not include_following and search_mode == "individual":
                    targets = await _resolve_fansly_targets(extra_names, unfollowed_only=False)
                    skip = username_keys(excluded)
                    targets = [
                        t for t in targets
                        if not matches_account(t.get("username"), t.get("accountId"), skip)
                    ]
                    if not targets and not announced_no_targets:
                        log.warning("No matching creators found to check for livestreams.")
                        announced_no_targets = True
                    online = await _streams_for_targets(targets)
                    selected = select_streams(online, active_usernames, excluded)
                    events.emit_sync("live_poll", state="targets", site="fansly", targets=targets)
                    warn_streak(streaks, "poll")
                    log_poll_state(selected)
                    return selected

                # Fetch followed online streams first, then fall back for unfollowed explicit targets
                online = await live_api.get_online_streams(c)
                selected = select_streams(online, active_usernames, excluded)
                explicit_targets = []

                if extra_names and search_mode != "list":
                    matched_keys = username_keys(
                        [s.get("username") for s in selected]
                        + [s.get("accountId") for s in selected]
                    )
                    skip = username_keys(excluded)
                    missing = [
                        u for u in extra_names
                        if u and str(u).lower() not in matched_keys and str(u).lower() not in skip
                    ]
                    if missing:
                        try:
                            explicit_targets = await _resolve_fansly_targets(
                                missing, unfollowed_only=(search_mode != "individual")
                            )
                            explicit_targets = [
                                t for t in explicit_targets
                                if not matches_account(t.get("username"), t.get("accountId"), skip)
                            ]
                            extra_online = await _streams_for_targets(explicit_targets)
                            seen_ids = {str(s["accountId"]) for s in selected}
                            for item in extra_online:
                                if str(item["accountId"]) not in seen_ids:
                                    seen_ids.add(str(item["accountId"]))
                                    selected.append(item)
                            warn_streak(streaks, "fallback")
                        except Exception as e:
                            warn_streak(streaks, "fallback", f"Fansly: checking extra creators failed: {e}")

                if opts["has_filters"] and selected:
                    unchecked = [
                        s for s in selected if str(s["accountId"]) not in filtered_cache
                    ]
                    if unchecked:
                        models = [
                            Model(m)
                            for m in await fansly_scrape.get_models(
                                [s["username"] for s in unchecked], c=c
                            )
                        ]
                        mm = getattr(manager.Manager, "model_manager", None) or ModelManager()
                        allowed_ids = {str(m.id) for m in mm.filter_models(models)}
                        returned = {str(m.id) for m in models}
                        for s in unchecked:
                            aid = str(s["accountId"])
                            if aid in returned:
                                filtered_cache[aid] = aid in allowed_ids
                    selected = [
                        s for s in selected if filtered_cache.get(str(s["accountId"]), False)
                    ]

                selected = select_streams(selected, active_usernames, excluded)
                merged_targets = {str(t["accountId"]): t for t in explicit_targets}
                for s in selected:
                    merged_targets[str(s["accountId"])] = {
                        "accountId": str(s["accountId"]),
                        "username": s["username"],
                    }
                events.emit_sync("live_poll", state="targets", site="fansly", targets=list(merged_targets.values()))
                warn_streak(streaks, "poll")
                log_poll_state(selected)
                return selected
            except Exception as e:
                warn_streak(streaks, "poll", f"Fansly livestream check failed: {e}")
                log.debug("", exc_info=True)
                raise

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
            if getattr(watcher, "chat_enabled", opts["chat"]):
                chat = live_chat.ChatRecorder(
                    live_chat.aiohttp_connect(auth.get("user_agent"), proxy),
                    auth.get("authorization_token"),
                    username=stream["username"],
                )
            await LiveRecorder(
                stream, save_location, fetch_channel, fetch_text, max_failures=opts["max_failures"],
                ffmpeg=ffmpeg, user_agent=auth.get("user_agent") or "", chat=chat,
                proxy=proxy,
            ).run(stop_event)

        raw_u = opts["usernames"]
        init_names = [raw_u] if isinstance(raw_u, str) else list(raw_u or [])
        watcher = LiveWatcher(
            fetch_online, record,
            max_concurrent=opts["max_concurrent"],
            interval=opts["interval"],
            jitter=opts["jitter"],
            once=not watch,
            site="fansly",
            chat_enabled=opts["chat"],
            include_following=wants_all_usernames(raw_u),
            extra_usernames=init_names,
            excluded_usernames=opts["excluded"],
        )
        await watcher.run(stop)
