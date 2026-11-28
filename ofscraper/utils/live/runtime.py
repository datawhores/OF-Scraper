"""Site-agnostic livestream watcher, thread runner, and shared helpers.

Used by both Fansly (``ofscraper.sites.fansly.live``) and OnlyFans
(``ofscraper.sites.onlyfans.live``) livestream recording.
"""

import asyncio
import datetime
import logging
import math
import random
import threading
import time

import ofscraper.utils.events as events
from ofscraper.utils.username_match import matches_account, username_keys

log = logging.getLogger("shared")

DEFAULT_INTERVAL = 60
DEFAULT_JITTER = 10
DEFAULT_MAX_CONCURRENT = 2
DEFAULT_MAX_FAILURES = 3

# with --refresh-users, the least time between two rereads of the creator
# lists in a live watch. Rereading on every check would scan every
# subscription once a minute.
REFRESH_USERS_SECONDS = 600


# ------------------------------------------------------------------ who is being recorded

# One set for the whole process: the one-shot --live run and the daemon's
# watch thread each have their own LiveWatcher and event loop, and must never
# record the same creator at the same time.
_RECORDING_LOCK = threading.Lock()
_RECORDING = set()


def claim(account_id) -> bool:
    """Mark a creator as being recorded; False if someone already is."""
    with _RECORDING_LOCK:
        if account_id in _RECORDING:
            return False
        _RECORDING.add(account_id)
        return True


def release(account_id):
    with _RECORDING_LOCK:
        _RECORDING.discard(account_id)


# ------------------------------------------------------------------ paths and selection

def utc_start(started_at) -> datetime.datetime:
    """Stream start in UTC from milliseconds or seconds; now when unknown."""
    if isinstance(started_at, datetime.datetime):
        return (
            started_at.astimezone(datetime.timezone.utc)
            if started_at.tzinfo
            else started_at.replace(tzinfo=datetime.timezone.utc)
        )
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
    import ofscraper.utils.paths.names as names
    from ofscraper.classes.of.base import base

    return names.clean_folder_name(base().file_cleanup(username))


def select_streams(online: list, usernames=None, excluded=None) -> list:
    """Live streams of the selected creators (all followed when none or ALL).

    ``usernames`` and ``excluded`` match a username in any case, an account id,
    or any name in ``looked_up_as`` (so ``-u oldname`` keeps a renamed creator).
    """

    def matches(stream, keys):
        if matches_account(stream.get("username"), stream.get("accountId"), keys):
            return True
        looked_up_as = stream.get("looked_up_as")
        return bool(looked_up_as) and not keys.isdisjoint(username_keys(looked_up_as))

    wanted = username_keys(usernames)
    skip = username_keys(excluded)
    out = [s for s in online if not matches(s, skip)]
    if not wanted or "all" in wanted:
        return out
    return [s for s in out if matches(s, wanted)]


# ------------------------------------------------------------------ watcher

class LiveWatcher:
    """Poll who is live and keep at most ``max_concurrent`` recordings running.

    ``fetch_online()`` returns the selected live streams; ``record(stream,
    stop)`` records one. Creators already being recorded aren't started twice;
    when a recording ends the next waiting creator starts straight away.
    """

    def __init__(
        self,
        fetch_online,
        record,
        max_concurrent=DEFAULT_MAX_CONCURRENT,
        interval=DEFAULT_INTERVAL,
        jitter=DEFAULT_JITTER,
        once=False,
        site: str = "fansly",
        chat_enabled: bool = False,
        include_following: bool | None = None,
        extra_usernames=None,
        excluded_usernames=None,
    ):
        self.fetch_online = fetch_online
        self.record = record
        self.max_concurrent = max(1, int(max_concurrent or 1))
        self.interval = interval
        self.jitter = jitter
        self.once = once
        self.site = site
        self.chat_enabled = bool(chat_enabled)
        self.include_following = None if include_following is None else bool(include_following)
        self.extra_usernames = (
            None
            if extra_usernames is None
            else {
                str(u).strip().lower()
                for u in extra_usernames
                if str(u).strip() and str(u).strip().upper() != "ALL"
            }
        )
        self.excluded_usernames = (
            None
            if excluded_usernames is None
            else {str(u).strip().lower() for u in excluded_usernames if str(u).strip()}
        )
        self.active = {}
        self.max_seen = 0
        self.paused = False
        self.suppressed = set()
        self.creator_stops = {}
        self._pending_resume = set()
        self._removed_ids = {}
        self._last_online = {}
        self._wake = None
        self._force_poll = False

    def effective_scope(self, opts: dict):
        """Return ``(include_following, extra_names, active_usernames, excluded)``
        combining runtime watcher overrides with ``opts`` defaults."""
        raw_u = opts.get("usernames")
        raw_ex = opts.get("excluded")
        w_inc = getattr(self, "include_following", None)
        include_following = wants_all_usernames(raw_u) if w_inc is None else bool(w_inc)
        w_extra = getattr(self, "extra_usernames", None)
        if w_extra is None:
            extra_list = [raw_u] if isinstance(raw_u, str) else list(raw_u or [])
            extra_names = sorted(
                {
                    str(u).strip().lower()
                    for u in extra_list
                    if str(u).strip() and str(u).strip().upper() != "ALL"
                }
            )
        else:
            extra_names = sorted(w_extra)
        w_excl = getattr(self, "excluded_usernames", None)
        excluded = raw_ex if w_excl is None else w_excl
        active_usernames = None if include_following else extra_names
        return include_following, extra_names, active_usernames, excluded

    def request_poll(self):
        self._force_poll = True
        if self._wake is not None:
            self._wake.set()

    def set_paused(self, paused: bool):
        self.paused = bool(paused)
        if not self.paused:
            self.request_poll()
        elif self._wake is not None:
            self._wake.set()

    def set_chat_enabled(self, enabled: bool):
        self.chat_enabled = bool(enabled)

    def set_max_concurrent(self, value: int):
        self.max_concurrent = max(1, int(value or 1))
        if self._wake is not None:
            self._wake.set()

    def _stop_one(
        self,
        key_str: str,
        *,
        stopped_reason: str = "Stopped by user (click [Resume] or press r)",
    ) -> bool:
        ev = self.creator_stops.get(key_str)
        info = self._last_online.get(key_str) or {}
        uname = info.get("username") or key_str
        if ev is not None and not ev.is_set():
            ev.set()
            events.emit_sync(
                "live_stream",
                site=self.site,
                account_id=key_str,
                username=uname,
                status="stopping",
                reason="Finalizing MP4 cleanly...",
            )
            return True
        # Not actively recording (was queued or online): mark stopped immediately
        events.emit_sync(
            "live_stream",
            site=self.site,
            account_id=key_str,
            username=uname,
            status="stopped",
            reason=stopped_reason,
        )
        return False

    def stop_creator(self, account_id) -> bool:
        key_str = str(account_id)
        self._pending_resume.discard(key_str)
        self.suppressed.add(key_str)
        was_active = self._stop_one(key_str)
        if not was_active and self._wake is not None:
            self._wake.set()
        return was_active

    def resume_creator(self, account_id):
        key_str = str(account_id)
        self.suppressed.discard(key_str)
        info = self._last_online.get(key_str) or {}
        uname = info.get("username") or key_str
        if key_str in self.active:
            # Old recording is still flushing to disk; queue automatic restart on exit
            self._pending_resume.add(key_str)
            events.emit_sync(
                "live_stream",
                site=self.site,
                account_id=key_str,
                username=uname,
                status="queued",
                reason="Waiting for previous part to finish closing...",
            )
            return
        events.emit_sync(
            "live_stream",
            site=self.site,
            account_id=key_str,
            username=uname,
            status="queued",
            reason="Resuming stream check...",
        )
        self.request_poll()

    def stop_all(self, account_ids=None) -> int:
        keys = {str(k) for k in (account_ids or []) if k is not None}
        keys |= set(self.creator_stops.keys())
        keys |= set(self.active.keys())
        keys |= set(self._last_online.keys())
        self._pending_resume.clear()
        self.suppressed |= keys
        stopped = sum(
            1
            for key_str in keys
            if self._stop_one(
                key_str, stopped_reason="Stopped by user (click [Resume] or press a)"
            )
        )
        if self._wake is not None:
            self._wake.set()
        return stopped

    def resume_all(self):
        skip = username_keys(self.excluded_usernames)
        removed_ids = {aid for ids in self._removed_ids.values() for aid in ids}
        to_resume = []
        for key_str in list(self.suppressed):
            info = self._last_online.get(key_str) or {}
            if key_str in removed_ids or matches_account(info.get("username"), key_str, skip):
                continue
            self.suppressed.discard(key_str)
            to_resume.append((key_str, info))
        for key_str, info in to_resume:
            uname = info.get("username") or key_str
            if key_str in self.active:
                self._pending_resume.add(key_str)
            events.emit_sync(
                "live_stream",
                site=self.site,
                account_id=key_str,
                username=uname,
                status="queued",
                reason="Resuming stream check...",
            )
        self.request_poll()

    def set_include_following(self, enabled: bool):
        self.include_following = bool(enabled)
        self.request_poll()

    def add_usernames(self, names):
        if self.extra_usernames is None:
            self.extra_usernames = set()
        if self.excluded_usernames is None:
            self.excluded_usernames = set()
        for raw in names or ():
            clean = str(raw).strip().lstrip("@").lower()
            if not clean or clean == "all":
                continue
            self.extra_usernames.add(clean)
            self.excluded_usernames.discard(clean)
            # the accounts the typed text stands for: the stopped creators it
            # names (by account id, or by the name they were last live under)
            # and the removed creators whose account id it is
            ids = set()
            for key_str in self.suppressed:
                info = self._last_online.get(key_str) or {}
                uname = str(info.get("username") or "").strip().lower()
                if key_str.lower() == clean or uname == clean:
                    ids.add(key_str)
            for removed in self._removed_ids.values():
                ids |= {key_str for key_str in removed if key_str.lower() == clean}
            # a creator removed under another name than the one typed (their
            # account id, say) is still left out by that name: forget it too
            for name in [n for n, removed in self._removed_ids.items() if n == clean or removed & ids]:
                self.excluded_usernames.discard(name)
                ids |= self._removed_ids.pop(name)
            for key_str in ids:
                self.excluded_usernames.discard(key_str.lower())
                self.suppressed.discard(key_str)
                if key_str in self.active:
                    # the recording stopped by the removal is still closing:
                    # check again as soon as it has, not on the next interval
                    self._pending_resume.add(key_str)
        self.request_poll()

    def remove_username(self, username: str, account_id=None):
        if self.extra_usernames is None:
            self.extra_usernames = set()
        if self.excluded_usernames is None:
            self.excluded_usernames = set()
        clean = str(username or "").strip().lstrip("@").lower()
        if clean:
            self.extra_usernames.discard(clean)
            self.excluded_usernames.add(clean)
        if account_id is not None:
            key_str = str(account_id)
            self.excluded_usernames.add(key_str.lower())
            if clean:
                self._removed_ids.setdefault(clean, set()).add(key_str)
            self._pending_resume.discard(key_str)
            self.suppressed.add(key_str)
            ev = self.creator_stops.get(key_str)
            if ev is not None:
                ev.set()

    def _start(self, stream, stop, wake) -> bool:
        key_str = str(stream["accountId"])
        self._last_online[key_str] = dict(stream)
        if not claim(key_str):
            log.debug(f"{stream.get('username')}: already being recorded")
            return False

        creator_stop = asyncio.Event()
        if stop.is_set():
            creator_stop.set()
        self.creator_stops[key_str] = creator_stop

        async def _forward_stop():
            await stop.wait()
            creator_stop.set()

        forwarder = asyncio.ensure_future(_forward_stop())

        async def runner():
            try:
                await self.record(stream, creator_stop)
            except Exception as e:
                log.info(f"{stream.get('username')}: livestream recording failed: {e}")
            finally:
                if not forwarder.done():
                    forwarder.cancel()
                await asyncio.gather(forwarder, return_exceptions=True)

        def _on_done(_task):
            if not forwarder.done():
                forwarder.cancel()
            self.creator_stops.pop(key_str, None)
            self.active.pop(key_str, None)
            release(key_str)
            if key_str in self._pending_resume and not stop.is_set():
                self._pending_resume.discard(key_str)
                self.suppressed.discard(key_str)
                self._force_poll = True
            elif key_str in self.suppressed and not stop.is_set():
                events.emit_sync(
                    "live_stream",
                    site=self.site,
                    account_id=key_str,
                    username=stream.get("username") or key_str,
                    status="stopped",
                    reason="Stopped by user (click [Resume] or press r)",
                )
            wake.set()

        task = asyncio.ensure_future(runner())
        task.add_done_callback(_on_done)
        self.active[key_str] = task
        self.max_seen = max(self.max_seen, len(self.active))
        return True

    async def run(self, stop: asyncio.Event = None):
        """Watch until ``stop``; with ``once`` only who is live now, then return."""
        stop = stop or asyncio.Event()
        wake = asyncio.Event()
        self._wake = wake
        loop = asyncio.get_running_loop()
        events.emit_sync(
            "live_watcher",
            state="started",
            watcher=self,
            loop=loop,
            site=self.site,
            once=self.once,
            interval=self.interval,
            jitter=self.jitter,
            max_concurrent=self.max_concurrent,
        )
        queue = []
        poll = True
        try:
            while not stop.is_set():
                wake.clear()
                if poll:
                    events.emit_sync("live_poll", state="polling", site=self.site)
                    try:
                        fetched = list(await self.fetch_online())
                        events.emit_sync(
                            "live_poll",
                            state="ok",
                            site=self.site,
                            online=fetched,
                            online_count=len(fetched),
                        )
                        for s in fetched:
                            self._last_online[str(s["accountId"])] = dict(s)
                        online_keys = {str(s["accountId"]) for s in fetched}
                        self.suppressed &= online_keys | set(self.active.keys())
                        for s in fetched:
                            if str(s["accountId"]) in self.suppressed and str(s["accountId"]) not in self.active:
                                events.emit_sync(
                                    "live_stream",
                                    site=self.site,
                                    account_id=str(s["accountId"]),
                                    username=s.get("username"),
                                    status="stopped",
                                    title=s.get("title"),
                                    started_at=s.get("startedAt"),
                                    reason="Paused by user (click [Resume] or press r)",
                                )
                        queue = [s for s in fetched if str(s["accountId"]) not in self.suppressed]
                    except Exception as e:
                        log.debug(f"live check failed: {e}")
                        events.emit_sync("live_poll", state="error", site=self.site, error=str(e))
                queue = [
                    s
                    for s in queue
                    if str(s["accountId"]) not in self.active and str(s["accountId"]) not in self.suppressed
                ]
                while not self.paused and queue and len(self.active) < self.max_concurrent:
                    self._start(queue.pop(0), stop, wake)
                for waiting in queue:
                    events.emit_sync(
                        "live_stream",
                        site=self.site,
                        account_id=str(waiting["accountId"]),
                        username=waiting.get("username"),
                        status="queued",
                        title=waiting.get("title"),
                        started_at=waiting.get("startedAt"),
                        reason=(
                            "Polls paused; starts when resumed"
                            if self.paused
                            else "Waiting for free recording slot"
                        ),
                    )
                if self.once:
                    if not queue and not self.active:
                        break
                    await _either(wake, stop)
                    if self._force_poll:
                        self._force_poll = False
                        poll = True
                    else:
                        poll = False
                    continue
                timeout = self.interval + random.uniform(0, self.jitter)
                events.emit_sync(
                    "live_poll",
                    state="waiting",
                    site=self.site,
                    timeout=timeout,
                    paused=self.paused,
                    max_concurrent=self.max_concurrent,
                )
                try:
                    await asyncio.wait_for(_either(wake, stop), timeout=timeout)
                    # a recording ended: start the next waiting creator now,
                    # the next poll still happens on the interval
                    if self._force_poll:
                        self._force_poll = False
                        poll = True
                    else:
                        poll = (not wake.is_set()) and (not self.paused)
                except asyncio.TimeoutError:
                    poll = not self.paused
        except asyncio.CancelledError:
            for task in self.active.values():
                task.cancel()
            raise
        finally:
            self._wake = None
            if self.active:
                await asyncio.gather(*self.active.values(), return_exceptions=True)
            events.emit_sync("live_watcher", state="stopped", watcher=self, site=self.site)


async def _either(a: asyncio.Event, b: asyncio.Event):
    tasks = [asyncio.ensure_future(a.wait()), asyncio.ensure_future(b.wait())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# ------------------------------------------------------------------ app glue

def _int_env(key: str, default: int, minimum: int = 1) -> int:
    import ofscraper.utils.of_env.of_env as of_env

    try:
        val = of_env.getattr(key, default)
        return max(minimum, int(default if val is None else val))
    except (TypeError, ValueError):
        return default


def _float_env(key: str, default: float, minimum: float = 0.0) -> float:
    import ofscraper.utils.of_env.of_env as of_env

    try:
        val = of_env.getattr(key, default)
        parsed = float(default if val is None else val)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(parsed):
        return float(default)
    return max(minimum, parsed)


def has_custom_user_filters(s=None) -> bool:
    """True when userlists, blacklists, or model filters narrow the creator pool."""
    from ofscraper.managers.model import ModelManager

    return ModelManager.has_active_filters(s)


def wants_all_usernames(usernames) -> bool:
    """True when --username was omitted or explicitly set to ALL."""
    if isinstance(usernames, str):
        return usernames.strip().upper() in ("", "ALL")
    names = [str(u).strip() for u in (usernames or []) if str(u).strip()]
    return not names or any(u.upper() == "ALL" for u in names)


def warn_streak(streaks: dict, key: str, message: str = None) -> None:
    """Log ``message`` as a warning at the start of a streak of failures and at
    debug after that; a call without a message ends the streak."""
    if message:
        (log.debug if streaks.get(key) else log.warning)(message)
    streaks[key] = bool(message)


class PollStateLogger:
    """Tracks announced live/idle state across poll cycles and logs transitions."""

    def __init__(self, site_name: str, watch: bool):
        self._site_name = site_name
        self._watch = watch
        self.announced_idle = False
        self.announced_live_ids = set()

    def __call__(self, selected) -> None:
        current_ids = {s["accountId"] for s in selected}
        self.announced_live_ids &= current_ids

        new_live = [s for s in selected if s["accountId"] not in self.announced_live_ids]
        if new_live:
            names = ", ".join(s["username"] for s in new_live)
            log.info(f"Live now ({len(new_live)}): {names}")
            self.announced_live_ids.update(s["accountId"] for s in new_live)
            self.announced_idle = False
        elif selected:
            names = ", ".join(s["username"] for s in selected)
            log.debug(f"Still live ({len(selected)}): {names}")
            self.announced_idle = False
        elif not self.announced_idle:
            if self._watch:
                log.info(
                    f"No active {self._site_name} livestreams; waiting for selected creators to go live..."
                )
            else:
                log.info(
                    f"No active {self._site_name} livestreams found for the selected creators."
                )
            self.announced_idle = True
        else:
            log.debug(f"No active {self._site_name} livestreams found.")


def lookup_due(misses: dict, name: str, poll: int) -> bool:
    """Whether to look up a name the lookups missed again on this poll: on
    every poll for its first 3 misses, then on every 10th poll."""
    return misses.get(name, 0) < 3 or poll % 10 == 0


def refresh_due(state: dict, now: float | None = None) -> bool:
    """With --refresh-users, whether this check reads the creator lists again:
    at most once per ``REFRESH_USERS_SECONDS``. The first call only starts the
    clock in ``state``, as the first check reads everything anyway."""
    now = time.monotonic() if now is None else now
    last = state.get("refreshed_at")
    if last is not None and now - last < REFRESH_USERS_SECONDS:
        return False
    state["refreshed_at"] = now
    return last is not None


def count_misses(misses: dict, tried, missing) -> None:
    """Record a lookup of the ``tried`` names: ``missing`` ones get one more
    miss, found ones are forgotten. A name reaching 3 misses is warned about once."""
    for name in tried:
        if name not in missing:
            misses.pop(name, None)
            continue
        misses[name] = misses.get(name, 0) + 1
        if misses[name] == 3:
            log.warning(f"Still can't look up {name} for livestreams; trying again every 10th check")


def _resolve_live_jitter(s) -> float:
    val = getattr(s, "live_jitter", None)
    if val is not None:
        try:
            parsed = float(val)
            if math.isfinite(parsed):
                return max(0.0, parsed)
        except (TypeError, ValueError):
            pass
    return _float_env("LIVE_JITTER", float(DEFAULT_JITTER), minimum=0.0)


def options(s=None) -> dict:
    """Livestream options from the merged settings (all default to off/brief values)."""
    import ofscraper.utils.args.globals as global_args
    import ofscraper.utils.settings as settings

    global_args_obj = global_args.args if s is None else None
    s = s or settings.get_settings()
    once = bool(getattr(s, "live", False))
    tui = bool(
        getattr(s, "live_tui", False)
        or (getattr(global_args_obj, "live_tui", False) if global_args_obj is not None else False)
    )
    watch = bool(getattr(s, "live_watch", False)) or (tui and not once)
    return {
        "once": once,
        "watch": watch,
        "tui": tui,
        "interval": getattr(s, "live_interval", None) or DEFAULT_INTERVAL,
        "max_concurrent": getattr(s, "live_max", None) or DEFAULT_MAX_CONCURRENT,
        "jitter": _resolve_live_jitter(s),
        "max_failures": _int_env("LIVE_MAX_FAILURES", DEFAULT_MAX_FAILURES, minimum=1),
        "check_concurrency": _int_env("LIVE_CHECK_CONCURRENCY", 5, minimum=1),
        "chat": bool(getattr(s, "live_chat", False)),
        "usernames": getattr(s, "usernames", None),
        "excluded": getattr(s, "excluded_username", None),
        "username_search": getattr(s, "username_search", None),
        "has_filters": has_custom_user_filters(s),
        "refresh_users": bool(getattr(s, "refresh_users", False)),
    }


def enabled(s=None) -> bool:
    """Whether --live or --live-watch was given (Fansly and OnlyFans profiles)."""
    opts = options(s)
    return opts["once"] or opts["watch"]


requested = enabled


def once_enabled(s=None) -> bool:
    return enabled(s) and options(s)["once"]


def watch_enabled(s=None) -> bool:
    return enabled(s) and options(s)["watch"]


def tui_enabled(s=None) -> bool:
    return bool(options(s).get("tui"))


def _default_runner(watch: bool, stop: asyncio.Event = None):
    from ofscraper.sites.fansly import live as fansly_live

    return fansly_live.run(watch, stop)


class LiveThread(threading.Thread):
    """Runs ``runner(watch, stop)`` on its own event loop so it can be stopped cleanly."""

    def __init__(self, watch: bool, runner=None, *, site: str | None = None):
        if site is None:
            try:
                import ofscraper.sites as sites

                resolved_site = sites.current_site()
            except Exception:
                resolved_site = None
        else:
            resolved_site = site
        name = f"{resolved_site}-live" if resolved_site else "live-watch"
        super().__init__(daemon=True, name=name)
        self.watch = watch
        self.runner = runner or _default_runner
        self.loop = None
        self.stop_event = None
        self.ready = threading.Event()
        self.finished = threading.Event()
        self.task = None

    def run(self):
        loop = asyncio.new_event_loop()
        self.loop = loop
        try:
            asyncio.set_event_loop(loop)
            self.stop_event = asyncio.Event()
            self.ready.set()
            self.task = loop.create_task(self.runner(self.watch, self.stop_event))
            loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass  # second Ctrl+C: runners force-stop their ffmpeg processes
        except Exception as e:
            log.info(f"livestream recording stopped: {e}")
            log.debug("", exc_info=True)
        finally:
            self.ready.set()
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            finally:
                loop.close()
                self.finished.set()

    def stop(self, timeout=30):
        log.warning("Stopping livestream recordings. A second Ctrl+C quits.")
        try:
            self._stop_recordings(timeout)
        except KeyboardInterrupt:
            self.force_stop()
            raise

    def _stop_recordings(self, timeout):
        self.ready.wait(5)
        loop = self.loop
        if loop is not None and self.stop_event is not None:
            try:
                loop.call_soon_threadsafe(self.stop_event.set)
            except RuntimeError:
                pass  # loop already closed
        self.finished.wait(timeout)

    def force_stop(self):
        if self.loop is not None and self.task is not None:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass  # loop already closed
        # On Windows an interrupted join can mark a still-running thread as
        # stopped. Wait for its loop cleanup independently of Thread's state.
        self.finished.wait(1)


def run_blocking(watch: bool, runner=None, menu=False, *, thread_cls=None):
    """Record in the foreground; Ctrl+C stops the recordings cleanly first."""
    import sys

    import ofscraper.utils.args.accessors.output as output_args

    if tui_enabled() and not output_args.low_output() and sys.stdout.isatty():
        from ofscraper.classes.live_tui import run_live_tui

        return run_live_tui(watch=watch, runner=runner, menu=menu)

    thread = (thread_cls or LiveThread)(watch, runner)
    thread.start()
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        thread.stop()
        if menu:
            return True
        raise SystemExit(130) from None


def start_watch_thread(runner=None, *, thread_cls=None) -> LiveThread:
    """Daemon mode: watch for livestreams beside the scheduled scrapes."""
    thread = (thread_cls or LiveThread)(True, runner)
    thread.start()
    return thread
