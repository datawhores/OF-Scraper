"""Record OnlyFans livestreams (``--live`` / ``--live-watch``).

Based on the Live Stream Monitor plugin by cjb900 (cjb900/OF-Scraper-GUI).

OnlyFans livestreams are WebRTC (Agora), not an HLS playlist ffmpeg could
read, so a recording is made by the stream page itself: a Chromium browser
(Playwright) opens it with the auth.json login and records the player with
the browser's MediaRecorder (see ``live_capture``).

- **Who is live:** an active subscription with ``hasStream`` set, from the
  same subscriptions list the scraper reads (or resolved once via ``retriver``
  when ``--username`` / ``-fi`` / ``-fl`` / user filters are given, then
  polled via ``users/{username}/streams/active``).
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
import pathlib
import threading
from urllib.parse import quote

from ofscraper.sites.fansly import live as shared
from ofscraper.utils.username_match import matches_account, username_keys

log = logging.getLogger("shared")

CHECK_TIMEOUT = 15
STREAM_ACTIVE_URL = "https://onlyfans.com/api2/v2/users/{}/streams/active?view=full_with_check"

_TARGET_CACHE: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_onlyfans_live_target_cache", default=None
)

_DEFAULT_LISTS = {"main", "ofscraper.main", "active", "ofscraper.active"}

_MODEL_FILTER_ATTRS = (
    "sub_status",
    "renewal",
    "current_price",
    "renewal_price",
    "regular_price",
    "promo_price",
    "last_seen",
    "free_trial",
    "promo",
    "all_promo",
    "promo_price_min",
    "promo_price_max",
    "regular_price_min",
    "regular_price_max",
    "current_price_min",
    "current_price_max",
    "renewal_price_min",
    "renewal_price_max",
    "last_seen_before",
    "last_seen_after",
    "expired_before",
    "expired_after",
    "subscribed_before",
    "subscribed_after",
)


def _has_custom_user_filters(s) -> bool:
    """True when custom userlists, blacklists, or model filters narrow the creator pool."""
    userlist = [
        x
        for x in (getattr(s, "userlist", None) or [])
        if x and str(x).lower() not in _DEFAULT_LISTS
    ]
    blacklist = [x for x in (getattr(s, "blacklist", None) or []) if x]
    if userlist or blacklist:
        return True
    return any(
        getattr(s, attr, None) not in (None, "", [], ())
        for attr in _MODEL_FILTER_ATTRS
    )


def _wants_all_usernames(usernames) -> bool:
    """True when --username was omitted or explicitly set to ALL."""
    names = [str(u) for u in (usernames or []) if u]
    return not names or any(u.upper() == "ALL" for u in names)


def recording_path(save_location, username, now=None) -> pathlib.Path:
    """``{save_location}/OnlyFans/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live.webm``"""
    now = now or datetime.datetime.now(tz=datetime.timezone.utc)
    username = shared.folder_name(username)
    folder = pathlib.Path(save_location) / "OnlyFans" / username / "Livestreams"
    return folder / f"{username}_{now.strftime('%Y%m%d_%H%M%S')}_live.webm"


def live_subscriptions(pages) -> list:
    """The creators in subscription pages who are live now, as watcher streams.

    Paging by offset can list a creator twice when subscriptions change
    during the scan, so each one is kept once.
    """
    out, seen = [], set()
    for page in pages:
        for user in page:
            if not (user.get("hasStream") and user.get("username")):
                continue
            key = user.get("id") or user.get("username")
            if key in seen:
                continue
            seen.add(key)
            out.append({"accountId": key, "username": user["username"]})
    return out


def stream_is_active(data):
    """True / False from a ``streams/active`` answer; None if it can't tell."""
    if not isinstance(data, dict):
        return None
    return bool(data.get("isActive")) and not data.get("isFinished")


async def _resolve_target_creators(usernames, excluded, all_users: bool, has_filters: bool) -> tuple[list, set]:
    """Resolve the creator list via retriver/filters; returns (targets, initial_live_keys)."""
    from ofscraper.data.models.utils import retriver
    from ofscraper.managers.model import ModelManager

    model_objs = await retriver.get_models()

    if has_filters and model_objs:
        mm = ModelManager()
        mm._update_all_subs(model_objs)
        model_objs = list(mm._filtered_models().values())

    if not all_users:
        import ofscraper.utils.username_match as username_match

        model_objs, _ = username_match.select_models(model_objs, usernames)

    skip = username_keys(excluded)
    targets, initial_live, seen = [], set(), set()
    for m in model_objs:
        raw = getattr(m, "model", {}) or {}
        username = getattr(m, "name", None) or raw.get("username")
        if not username:
            continue
        key = getattr(m, "id", None) or raw.get("id") or username
        if key in seen or matches_account(username, key, skip):
            continue
        seen.add(key)
        targets.append({"accountId": key, "username": username})
        if raw.get("hasStream"):
            initial_live.add(key)

    return targets, initial_live


async def get_online_streams(c) -> list:
    import ofscraper.utils.settings as settings
    from ofscraper.data.api.subscriptions.subscriptions import scrape_subscriptions_active

    s = settings.get_settings()
    opts = shared.options()
    usernames = opts.get("usernames") if opts.get("usernames") is not None else getattr(s, "usernames", None)
    excluded = opts.get("excluded") if opts.get("excluded") is not None else getattr(s, "excluded_username", None)
    all_users = _wants_all_usernames(usernames)
    has_filters = _has_custom_user_filters(s)

    # Default when --username is omitted (or ALL) and no custom filters are active:
    # grab every live creator from active subscriptions in batch pages.
    if all_users and not has_filters:
        pages = [page async for page in scrape_subscriptions_active(c)]
        return live_subscriptions(pages)

    cache = _TARGET_CACHE.get()
    if cache is None:
        cache = {}

    # When --username is omitted (or ALL) WITH custom filters (e.g. --user-list),
    # cache the filtered creator IDs once and read hasStream from batch subscription pages.
    if all_users:
        if "filtered_ids" not in cache:
            targets, initial_live = await _resolve_target_creators(
                usernames, excluded, all_users=True, has_filters=True
            )
            cache["filtered_ids"] = {t["accountId"] for t in targets}
            if not targets:
                log.warning("No matching creators found to check for livestreams.")
                return []
            return [t for t in targets if t["accountId"] in initial_live]

        allowed_ids = cache["filtered_ids"]
        if not allowed_ids:
            return []
        pages = [page async for page in scrape_subscriptions_active(c)]
        return [s for s in live_subscriptions(pages) if s["accountId"] in allowed_ids]

    # When specific --username targets are given (-fi, -fl, or auto-threshold),
    # resolve the target accounts once and poll streams/active for each target.
    initial_live = set()
    if "targets" not in cache:
        targets, initial_live = await _resolve_target_creators(
            usernames, excluded, all_users=False, has_filters=has_filters
        )
        cache["targets"] = targets
        if not targets:
            log.warning("No matching creators found to check for livestreams.")
            return []

    online = []
    for target in cache["targets"]:
        if target["accountId"] in initial_live or await still_live(c, target["username"]):
            online.append(target)
    return online


async def still_live(c, username):
    """True / False from OnlyFans; None when the check fails."""
    try:
        async with c.requests_async(url=STREAM_ACTIVE_URL.format(quote(username, safe=""))) as r:
            if r.status == 404:
                return False
            if not (200 <= r.status < 300):
                return None
            return stream_is_active(await r.json_())
    except Exception as e:
        log.debug(f"{username}: live check failed: {e}")
        return None


async def record_in_thread(capture, stop: asyncio.Event, **kwargs):
    """Run the blocking ``capture(halt=...)`` in a thread; ``stop`` sets ``halt``."""
    halt = threading.Event()
    job = asyncio.ensure_future(asyncio.to_thread(capture, halt=halt, **kwargs))
    try:
        while not job.done():
            if stop.is_set():
                halt.set()
            await asyncio.wait({job}, timeout=1)
    finally:
        # also on Ctrl+C: the browser saves what it has before the thread ends
        halt.set()
        if not job.done():
            await asyncio.wait({job}, timeout=60)
    return job.result()


async def run(watch: bool = False, stop: asyncio.Event = None):
    """Record the selected creators who are live: once, or watching until stopped."""
    import ofscraper.managers.manager as manager
    import ofscraper.utils.paths.common as common_paths
    import ofscraper.utils.system.ffmpeg as ffmpeg_finder
    from ofscraper.sites.onlyfans import live_capture
    from ofscraper.utils.auth.file import read_auth
    import ofscraper.utils.of_env.of_env as of_env

    opts = shared.options()
    if opts["chat"]:
        log.warning("--live-chat only applies to Fansly; OnlyFans recordings have no chat file")
    if not live_capture.playwright_ready():
        return
    save_location = common_paths.get_save_location()
    ffmpeg = ffmpeg_finder.get_ffmpeg()

    if watch:
        log.info(
            f"Watching for OnlyFans livestreams (polling every {opts['interval']}s, "
            f"up to {opts['max_concurrent']} concurrent)..."
        )
    else:
        log.info("Checking for active OnlyFans livestreams...")

    cache_token = _TARGET_CACHE.set({})
    try:
        # live checks get one attempt: a failed check counts as "don't know" and
        # the next one comes a minute later, so retries would only hold up the recording
        async with manager.Manager.session.aget_ofsession() as c, \
                manager.Manager.session.aget_ofsession(retries=1) as checks:
            loop = asyncio.get_running_loop()
            warned = []
            announced_idle = False
            watcher = None

            async def fetch_online():
                nonlocal announced_idle
                try:
                    online = await get_online_streams(c)
                except Exception as e:
                    log.warning(f"OnlyFans livestream check failed: {e}")
                    log.debug("", exc_info=True)
                    raise
                selected = shared.select_streams(online, opts["usernames"], opts["excluded"])
                active_ids = watcher.active if watcher is not None else {}
                new_live = [s for s in selected if s["accountId"] not in active_ids]
                if new_live:
                    names = ", ".join(s["username"] for s in new_live)
                    log.info(f"Live now ({len(new_live)}): {names}")
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

            async def record(stream, stop_event):
                username = stream["username"]

                def check_live():
                    future = asyncio.run_coroutine_threadsafe(still_live(checks, username), loop)
                    try:
                        return future.result(timeout=CHECK_TIMEOUT)
                    except Exception:
                        future.cancel()
                        return None

                try:
                    await record_in_thread(
                        live_capture.capture, stop_event,
                        username=username,
                        out=recording_path(save_location, username),
                        # read each time: auth.json may be renewed during --live-watch
                        auth=read_auth(),
                        still_live=check_live,
                        ffmpeg=ffmpeg,
                        proxy=of_env.getattr("PROXY"),
                    )
                except live_capture.BrowserMissing as e:
                    # once per run: --live-watch tries again every interval
                    (log.debug if warned else log.warning)(str(e))
                    warned.append(True)

            watcher = shared.LiveWatcher(
                fetch_online, record,
                max_concurrent=opts["max_concurrent"],
                interval=opts["interval"],
                once=not watch,
            )
            await watcher.run(stop)
    finally:
        _TARGET_CACHE.reset(cache_token)