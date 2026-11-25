"""Record OnlyFans livestreams (``--live`` / ``--live-watch``).

Based on the Live Stream Monitor plugin by cjb900 (cjb900/OF-Scraper-GUI).

OnlyFans livestreams are WebRTC (Agora), not an HLS playlist ffmpeg could
read, so a recording is made by the stream page itself: a Chromium browser
(Playwright) opens it with the auth.json login and records the player with
the browser's MediaRecorder (see ``live_capture``).

- **Who is live:** an active subscription with ``hasStream`` set, from the
  same subscriptions list the scraper reads. Creators chosen with ``-u`` and
  the individual search are asked one by one with the still-live check.
- **Still live:** ``users/{username}/streams/active``, asked while recording.

Recordings go to
``{save_location}/OnlyFans/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live.webm``.
The watcher, the Ctrl+C handling and the options are shared with Fansly
(``ofscraper.sites.fansly.live``).
"""

import asyncio
import contextvars
import datetime
import logging
import os
import pathlib
import threading
from urllib.parse import quote

import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.ffmpeg as ffmpeg_finder
from ofscraper.sites.fansly import live as shared
from ofscraper.sites.onlyfans import live_capture
from ofscraper.utils import username_match

log = logging.getLogger("shared")

_TARGET_CACHE: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_onlyfans_live_target_cache", default=None
)


def _check_timeout() -> int:
    return max(1, int(of_env.getattr("LIVE_CHECK_TIMEOUT")))


def _check_concurrency() -> int:
    return max(1, int(of_env.getattr("LIVE_CHECK_CONCURRENCY")))


def _jitter() -> int:
    try:
        val = of_env.getattr("LIVE_JITTER", 10)
        return max(0, int(10 if val is None else val))
    except (TypeError, ValueError):
        return 10


def _stream_active_url(username: str) -> str:
    return of_env.getattr("STREAM_ACTIVE_URL").format(quote(username, safe=""))


def live_subscriptions(pages: list) -> list:
    """Subscriptions currently streaming from scraped active-subscription pages."""
    out = []
    seen = set()
    for page in pages or ():
        for user in page or ():
            if not isinstance(user, dict) or not user.get("hasStream"):
                continue
            username = user.get("username")
            uid = user.get("id")
            if uid is None:
                uid = username
            if uid is None or not username or uid in seen:
                continue
            seen.add(uid)
            out.append({"accountId": uid, "username": username})
    return out


def stream_is_active(payload):
    """True / False if OnlyFans' streams/active response says live/ended; None if invalid."""
    if not isinstance(payload, dict):
        return None
    if payload.get("isFinished"):
        return False
    return bool(payload.get("isActive"))


async def still_live(c, username):
    """True / False from OnlyFans; None when the check fails."""
    try:
        async with c.requests_async(url=_stream_active_url(username)) as r:
            if r.status == 404:
                return False
            if not (200 <= r.status < 300):
                return None
            return stream_is_active(await r.json_())
    except Exception as e:
        log.debug(f"{username}: live check failed: {e}")
        return None


async def _resolve_target_creators(usernames, excluded, all_users: bool, has_filters: bool):
    """Resolve target creators once via retriver + ModelManager, returning (targets, initially_live_ids)."""
    import ofscraper.data.models.utils.retriver as retriver

    models = await retriver.get_models()
    if has_filters and models:
        mm = getattr(manager.Manager, "model_manager", None)
        if mm is None:
            from ofscraper.managers.model import ModelManager

            mm = ModelManager()
        models = mm.filter_models(models)

    # the scraper's matcher: a renamed creator also matches the name it was looked up as (#662)
    wanted = username_match.username_keys(None if all_users else usernames)
    skip = username_match.username_keys(excluded)
    targets, initially_live = [], set()
    for m in models or ():
        if username_match.model_matches(m, skip):
            continue
        if wanted and "all" not in wanted and not username_match.model_matches(m, wanted):
            continue
        target = {"accountId": m.id, "username": m.name}
        looked_up_as = m.model.get("looked_up_as")
        if looked_up_as:
            target["looked_up_as"] = list(looked_up_as)
        targets.append(target)
        if m.model.get("hasStream"):
            initially_live.add(m.id)
    return targets, initially_live


def select_streams(online: list, usernames=None, excluded=None) -> list:
    """``shared.select_streams``, also matching a stream by the name its creator
    was looked up as, so ``-u oldname`` keeps a renamed creator (#662)."""

    def matches(stream, keys):
        return username_match.matches_account(
            stream.get("username"), stream.get("accountId"), keys
        ) or not keys.isdisjoint(username_match.username_keys(stream.get("looked_up_as")))

    wanted = username_match.username_keys(usernames)
    skip = username_match.username_keys(excluded)
    out = [s for s in online if not matches(s, skip)]
    if not wanted or "all" in wanted:
        return out
    return [s for s in out if matches(s, wanted)]


async def _check_targets_concurrently(check_session, targets, initial_live: set) -> list:
    """Check cached targets concurrently on the single-attempt session."""
    sem = asyncio.Semaphore(_check_concurrency())

    async def check_one(target):
        if target["accountId"] in initial_live:
            return target
        async with sem:
            if await still_live(check_session, target["username"]):
                return target
        return None

    results = await asyncio.gather(
        *(check_one(t) for t in targets),
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, dict)]


async def get_online_streams(c, checks=None) -> list:
    import ofscraper.utils.settings as settings
    from ofscraper.data.api.subscriptions.subscriptions import scrape_subscriptions_active

    s = settings.get_settings()
    opts = shared.options()
    usernames = opts.get("usernames") if opts.get("usernames") is not None else getattr(s, "usernames", None)
    excluded = opts.get("excluded") if opts.get("excluded") is not None else getattr(s, "excluded_username", None)
    search_mode = (
        opts.get("username_search")
        if opts.get("username_search") is not None
        else getattr(s, "username_search", None)
    )
    all_users = shared.wants_all_usernames(usernames)
    has_filters = shared.has_custom_user_filters(s)
    check_session = checks or c

    # Default when --username is omitted (or ALL) and no custom filters are active:
    # grab every live creator from active subscriptions in batch pages.
    if all_users and not has_filters:
        pages = [page async for page in scrape_subscriptions_active(c)]
        return live_subscriptions(pages)

    cache = _TARGET_CACHE.get()
    if cache is None:
        cache = {}

    # Batch subscription path:
    # - ALL with custom filters (--user-list, price/date filters, etc.)
    # - Explicit --username with -fl (--username-list-search)
    if all_users or search_mode == "list":
        if "filtered_ids" not in cache:
            targets, initial_live = await _resolve_target_creators(
                usernames, excluded, all_users=all_users, has_filters=has_filters
            )
            cache["filtered_ids"] = {t["accountId"]: t for t in targets}
            if not targets:
                log.warning("No matching creators found to check for livestreams.")
                return []
            return [t for t in targets if t["accountId"] in initial_live]

        allowed_ids = cache["filtered_ids"]
        if not allowed_ids:
            return []
        pages = [page async for page in scrape_subscriptions_active(c)]
        # the cached target, which keeps the name a renamed creator was looked up as
        return [allowed_ids[s["accountId"]] for s in live_subscriptions(pages) if s["accountId"] in allowed_ids]

    # Individual target path (-fi or auto-selected individual search):
    # resolve target accounts once, then poll streams/active concurrently on `checks` (retries=1).
    initial_live = set()
    if "targets" not in cache:
        targets, initial_live = await _resolve_target_creators(
            usernames, excluded, all_users=False, has_filters=has_filters
        )
        cache["targets"] = targets
        if not targets:
            log.warning("No matching creators found to check for livestreams.")
            return []

    return await _check_targets_concurrently(check_session, cache["targets"], initial_live)


def recording_path(save_location, username: str, when: datetime.datetime | None = None) -> pathlib.Path:
    when = when or datetime.datetime.now(datetime.timezone.utc)
    stamp = when.strftime("%Y%m%d_%H%M%S")
    username = shared.folder_name(username)
    return (
        pathlib.Path(save_location)
        / "OnlyFans"
        / username
        / "Livestreams"
        / f"{username}_{stamp}_live.webm"
    )


async def record_in_thread(fn, stop_event: asyncio.Event, *args, **kwargs):
    halt = threading.Event()
    if args:
        job = asyncio.ensure_future(asyncio.to_thread(fn, halt, *args, **kwargs))
    else:
        job = asyncio.ensure_future(asyncio.to_thread(fn, halt=halt, **kwargs))
    try:
        while not job.done():
            if stop_event.is_set():
                halt.set()
            await asyncio.wait({job}, timeout=1)
    finally:
        # also on Ctrl+C: the browser saves what it has before the thread ends
        halt.set()
        if not job.done():
            await asyncio.wait({job}, timeout=60)
    return job.result()


def _session_proxy(c) -> str | None:
    return getattr(c, "proxy", None)


async def run(watch: bool, stop: asyncio.Event | None = None):
    """Check once (--live) or watch (--live-watch) and record OnlyFans streams."""
    opts = shared.options()
    if opts["chat"]:
        log.warning("--live-chat only applies to Fansly; ignoring it for OnlyFans.")

    if not live_capture.playwright_ready():  # logs how to install it
        return

    save_location = common_paths.get_save_location()
    ffmpeg = ffmpeg_finder.get_ffmpeg() or None
    cache_token = _TARGET_CACHE.set({})

    try:
        # Separate sessions: `c` retries batch list calls; `checks` gets one attempt
        # per live status check so a transient failure doesn't stall polling.
        async with manager.Manager.session.aget_ofsession() as c, \
                manager.Manager.session.aget_ofsession(retries=1) as checks:
            loop = asyncio.get_running_loop()
            warned = []
            announced_idle = False
            announced_live_ids = set()
            poll_failed = False

            async def fetch_online():
                nonlocal announced_idle, announced_live_ids, poll_failed
                try:
                    online = await get_online_streams(c, checks=checks)
                except Exception as e:
                    if not poll_failed:
                        log.warning(f"OnlyFans livestream check failed: {e}")
                        poll_failed = True
                    else:
                        log.debug(f"OnlyFans livestream check failed: {e}")
                    log.debug("", exc_info=True)
                    raise

                poll_failed = False
                selected = select_streams(online, opts["usernames"], opts["excluded"])
                current_ids = {s["accountId"] for s in selected}
                announced_live_ids &= current_ids

                new_live = [s for s in selected if s["accountId"] not in announced_live_ids]
                if new_live:
                    names = ", ".join(s["username"] for s in new_live)
                    log.info(f"Live now ({len(new_live)}): {names}")
                    announced_live_ids.update(s["accountId"] for s in new_live)
                    announced_idle = False
                elif selected:
                    names = ", ".join(s["username"] for s in selected)
                    log.debug(f"Still live ({len(selected)}): {names}")
                    announced_idle = False
                elif not announced_idle:
                    if watch:
                        log.info("No active OnlyFans livestreams; waiting for selected creators to go live...")
                    else:
                        log.info("No active OnlyFans livestreams found for the selected creators.")
                    announced_idle = True
                else:
                    log.debug("No active OnlyFans livestreams found.")
                return selected

            def check_live(username: str):
                future = asyncio.run_coroutine_threadsafe(still_live(checks, username), loop)
                try:
                    return future.result(timeout=_check_timeout())
                except Exception as e:
                    log.debug(f"{username}: live check timed out/failed: {e}")
                    future.cancel()
                    return None

            async def record(stream: dict, stop_event: asyncio.Event):
                import ofscraper.utils.auth.file as auth_file

                username = stream["username"]
                out = recording_path(save_location, username)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                auth = auth_file.read_auth()
                proxy = _session_proxy(c)
                try:
                    log.info(f"Recording OnlyFans livestream for {username} -> {out}")
                    await record_in_thread(
                        live_capture.capture,
                        stop_event,
                        username=username,
                        out=out,
                        auth=auth,
                        still_live=lambda: check_live(username),
                        ffmpeg=ffmpeg,
                        proxy=proxy,
                    )
                    log.info(f"Finished OnlyFans livestream recording for {username}")
                except live_capture.BrowserMissing as e:
                    if not warned:
                        warned.append(True)
                        log.warning(str(e))
                except Exception as e:
                    log.warning(f"{username}: livestream recording failed: {e}")
                    log.debug("", exc_info=True)

            if watch:
                log.info(
                    f"Watching for OnlyFans livestreams (interval={opts['interval']}s, max_concurrent={opts['max_concurrent']})..."
                )
            else:
                log.info("Checking for active OnlyFans livestreams...")

            watcher = shared.LiveWatcher(
                fetch_online,
                record,
                max_concurrent=opts["max_concurrent"],
                interval=opts["interval"],
                jitter=opts.get("jitter", _jitter()),
                once=not watch,
            )
            await watcher.run(stop)
    finally:
        _TARGET_CACHE.reset(cache_token)
