"""Record OnlyFans livestreams (``--live`` / ``--live-watch``).

Based on the Live Stream Monitor plugin by cjb900 (cjb900/OF-Scraper-GUI).

OnlyFans livestreams are WebRTC (Agora), not an HLS playlist ffmpeg could
read, so a recording is made by the stream page itself: a Chromium browser
(Playwright) opens it with the auth.json login and records the player with
the browser's MediaRecorder (see ``live_capture``).

- **Who is live:** an active subscription with ``hasStream`` set, from the
  same subscriptions list the scraper reads. Creators chosen with ``-u`` and
  the individual search are asked one by one with the still-live check, up
  to ``LIVE_INDIVIDUAL_MAX`` of them, as are chosen creators who aren't
  active subscriptions.
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
import ofscraper.utils.events as events
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
_WATCHER: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "_onlyfans_live_watcher", default=None
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


async def _list_members(names) -> list:
    """Members of custom lists or built-in subscription lists, read strictly."""
    import ofscraper.data.api.subscriptions.lists as lists
    import ofscraper.data.api.subscriptions.subscriptions as subscriptions
    from ofscraper.managers.model import ModelManager

    names = {str(n).strip().lower() for n in names or () if str(n).strip()}
    if not names:
        return []
    reserved = ModelManager.built_in_lists("RESERVED")
    active = bool(names & (reserved | ModelManager.built_in_lists("ACTIVE")))
    expired = bool(names & (reserved | ModelManager.built_in_lists("EXPIRED")))
    custom = names - ModelManager.built_in_lists("RESERVED", "ACTIVE", "EXPIRED")
    chosen = [x for x in await lists.get_lists(strict=True) if str(x.get("name")).lower() in custom] if custom else []
    members = await lists.get_list_users(chosen, strict=True) if chosen else []
    if active or expired:
        async with manager.Manager.session.aget_subscription_session(
            sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
        ) as c:
            if active:
                async for page in subscriptions.scrape_subscriptions_active(c, strict=True):
                    members.extend(page)
            if expired:
                async for page in subscriptions.scrape_subscriptions_disabled(c, strict=True):
                    members.extend(page)
    return members


async def _fetch_models(c, cache: dict, names=None) -> list:
    """The creators to choose targets from: ``names`` looked up one by one, or
    else the active and expired subscriptions and the members of the lists
    chosen with --user-list. Read like the scraper's retriever does, but
    without its screen updates or its subscriber count request, which would
    hold up this loop. The creators a list names are kept for _direct_targets."""
    import ofscraper.data.api.subscriptions.individual as individual
    import ofscraper.data.api.subscriptions.subscriptions as subscriptions
    from ofscraper.classes.of.models import Model
    from ofscraper.managers.model import ModelManager

    if names is not None:
        return [Model(x) for x in await individual.get_subscription(list(names))]
    chosen = ModelManager.user_lists()
    members = await _list_members(chosen - ModelManager.built_in_lists("RESERVED", "ACTIVE", "EXPIRED"))
    expired = await subscriptions.expiredHelper(None, c, strict=True)
    named = members + (expired if chosen & ModelManager.built_in_lists("EXPIRED") else [])
    cache["named_ids"] = {u.get("id") for u in named}
    found = await subscriptions.activeHelper(None, c, strict=True) + expired
    return [Model(x) for x in found + members]


async def _resolve_target_creators(usernames, excluded, all_users: bool, has_filters: bool, models, cache: dict):
    """Choose the target creators from ``models``, returning (targets,
    initially_live_ids, unresolved). ``unresolved`` lists the -u names no
    creator came back for, or is None when no creator came back at all. A
    creator on a ``--black-list`` list counts as found and left out."""
    import ofscraper.utils.settings as settings

    if all_users:
        unresolved = None if not models else []
    else:
        names = [usernames] if isinstance(usernames, str) else list(usernames or [])
        _, unresolved = username_match.select_models(models or [], names)
    if "blacklist_ids" not in cache:
        black = getattr(settings.get_settings(), "blacklist", None)
        cache["blacklist_ids"] = {u.get("id") for u in await _list_members(black)}
    models = [m for m in models or () if m.id not in cache["blacklist_ids"]]
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
    return targets, initially_live, unresolved


async def _look_up_names(c, names, excluded, has_filters: bool, cache: dict):
    """Look up -u names one by one: (targets, initially_live_ids, unresolved)."""
    models = await _fetch_models(c, cache, names)
    return await _resolve_target_creators(names, excluded, False, has_filters, models, cache)


# the name the lookups of all subscriptions are counted under for the backoff
_ALL = "the creator list"


async def _update_targets(c, cache: dict, usernames, excluded, all_users: bool, has_filters: bool, by_name: bool) -> set:
    """Look up the target creators into ``cache["targets"]``: all of them on the
    first poll (the -u names one by one with ``by_name``, else from the
    subscription lists), then on later polls the ones a failed lookup left
    out, so one failure doesn't leave a creator unwatched all session.
    Returns the ids the lookup saw live."""
    # the cache is filled only after a lookup succeeds: one that raised leaves
    # it as it was, so the next poll looks up everything again
    cache["poll"] = poll = cache.get("poll", 0) + 1
    misses = cache.setdefault("misses", {})
    if "targets" not in cache or cache["unresolved"] is None:
        # a lookup that keeps finding no creators at all is made less often too
        if "targets" in cache and not shared.lookup_due(misses, _ALL, poll):
            return set()
        names = None if all_users else ([usernames] if isinstance(usernames, str) else list(usernames))
        models = await _fetch_models(c, cache, names if by_name else None)
        targets, initial_live, unresolved = await _resolve_target_creators(
            usernames, excluded, all_users, has_filters, models, cache
        )
        # -u names the lists don't have, such as a creator's old name, are
        # looked up one by one, as the scraper does (#662)
        if unresolved and not by_name:
            more, more_live, unresolved = await _look_up_names(c, unresolved, excluded, has_filters, cache)
            targets, initial_live = targets + more, initial_live | more_live
        tried = [_ALL, *(unresolved or [])]
        shared.count_misses(misses, tried, tried if unresolved is None else unresolved)
    elif cache["unresolved"]:
        # a name that keeps missing (a typo, a deleted account) is asked less often
        due = [n for n in cache["unresolved"] if shared.lookup_due(misses, n, poll)]
        if not due:
            return set()
        targets, initial_live, missing = await _look_up_names(c, due, excluded, has_filters, cache)
        shared.count_misses(misses, due, missing)
        unresolved = [n for n in cache["unresolved"] if n not in due] + missing
    else:
        return set()

    cache.setdefault("targets", {}).update({t["accountId"]: t for t in targets})
    cache["unresolved"] = unresolved
    if unresolved is None or unresolved:
        missing = "the creator list" if unresolved is None else ", ".join(map(str, unresolved))
        import ofscraper.utils.settings as settings

        again = "; trying again on the next check" if getattr(settings.get_settings(), "live_watch", False) else ""
        (log.debug if cache.get("warned") else log.warning)(
            f"Could not look up {missing} to check for livestreams{again}"
        )
        cache["warned"] = True
    elif not cache["targets"]:
        log.warning("No matching creators found to check for livestreams.")
    return initial_live


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


async def _check_targets_concurrently(check_session, targets, initial_live: set, cache=None) -> list:
    """Check cached targets concurrently on the single-attempt session.

    A check that fails counts as offline; that is warned about once until
    the checks work again (``cache`` keeps the streak across polls)."""
    sem = asyncio.Semaphore(_check_concurrency())
    failed = []

    async def check_one(target):
        if target["accountId"] in initial_live:
            return target
        async with sem:
            answer = await still_live(check_session, target["username"])
        if answer is None:
            failed.append(target["username"])
        return target if answer else None

    results = await asyncio.gather(
        *(check_one(t) for t in targets),
        return_exceptions=True,
    )
    shared.warn_streak(cache if cache is not None else {}, "checks", failed and (
        f"OnlyFans live check failed for {len(failed)} creator(s); "
        "they count as offline until a check works"
    ))
    return [r for r in results if isinstance(r, dict)]


def _individual_max() -> int:
    return max(0, int(of_env.getattr("LIVE_INDIVIDUAL_MAX")))


def _direct_targets(cache: dict, all_users: bool, targets: dict, pages: list, live_ids: set) -> list:
    """The targets to ask one by one this poll: those missing from the active
    list (expired, or only on a user list) that were chosen by name, at most
    LIVE_INDIVIDUAL_MAX of them, taking turns across polls.

    Chosen by name: every target with -u; without it, the members of the
    user's own lists chosen with --user-list, and the expired subscriptions
    with --user-list expired. Other filters choose from the subscriptions, so
    only active subscriptions are watched then. Empty ``pages`` is an account
    with no active subscriptions: a failed read raises before this."""
    named = cache.get("named_ids", set()) if all_users else set(targets)
    if all_users and not named and not cache.get("told"):
        cache["told"] = True
        log.info("Without -u or a user list, only active subscriptions are checked for livestreams")
    listed = {u.get("id") for page in pages for u in page or () if isinstance(u, dict)}
    missing = [
        t for t in targets.values()
        if t["accountId"] in named and t["accountId"] not in listed | live_ids
    ]
    most = _individual_max()
    if len(missing) <= most:
        return missing
    start = cache.get("turn", 0) % len(missing)
    cache["turn"] = start + most
    return (missing + missing)[start:start + most]


def _get_extra_cache(cache: dict, extra, excluded) -> dict:
    extra_cache = cache.setdefault("_extra", {})
    extra_sig = (
        tuple(sorted(username_match.username_keys(extra))),
        tuple(sorted(username_match.username_keys(excluded))),
    )
    if extra_cache.get("_sig") != extra_sig:
        extra_cache.clear()
        extra_cache["_sig"] = extra_sig
    return extra_cache


async def get_online_streams(c, checks=None) -> list:
    import ofscraper.utils.settings as settings
    from ofscraper.data.api.subscriptions.subscriptions import scrape_subscriptions_active

    s = settings.get_settings()
    opts = shared.options()
    watcher = _WATCHER.get()
    extra = []
    raw_u = opts.get("usernames") if opts.get("usernames") is not None else getattr(s, "usernames", None)
    raw_ex = opts.get("excluded") if opts.get("excluded") is not None else getattr(s, "excluded_username", None)
    if watcher is not None and getattr(watcher, "include_following", None) is not None:
        all_users = bool(watcher.include_following)
        w_extra = getattr(watcher, "extra_usernames", None)
        if w_extra is None:
            extra_list = [raw_u] if isinstance(raw_u, str) else list(raw_u or [])
            extra = sorted({
                str(u).strip().lower() for u in extra_list
                if str(u).strip() and str(u).strip().upper() != "ALL"
            })
        else:
            extra = sorted(w_extra)
        usernames = None if all_users else extra
        w_excl = getattr(watcher, "excluded_usernames", None)
        excluded = raw_ex if w_excl is None else w_excl
        if not all_users and not extra:
            events.emit_sync("live_poll", state="targets", site="onlyfans", targets=[])
            return []
    else:
        usernames = raw_u
        excluded = raw_ex
        all_users = shared.wants_all_usernames(usernames)
    search_mode = (
        opts.get("username_search")
        if opts.get("username_search") is not None
        else getattr(s, "username_search", None)
    )
    has_filters = shared.has_custom_user_filters(s)
    check_session = checks or c

    # Default when --username is omitted (or ALL) and no custom filters are active:
    # grab every live creator from active subscriptions in batch pages.
    if all_users and not has_filters and not extra:
        pages = [page async for page in scrape_subscriptions_active(c)]
        live = live_subscriptions(pages)
        events.emit_sync("live_poll", state="targets", site="onlyfans", targets=live)
        return live

    cache = _TARGET_CACHE.get()
    if cache is None:
        cache = {}

    if all_users and not has_filters and extra:
        pages = [page async for page in scrape_subscriptions_active(c)]
        live = live_subscriptions(pages)
        extra_cache = _get_extra_cache(cache, extra, excluded)
        extra_live_ids = await _update_targets(
            c, extra_cache, extra, excluded, False, False, True
        )
        extra_targets = extra_cache.get("targets") or {}
        seen_ids = {str(x["accountId"]) for x in live}
        to_check = [t for t in extra_targets.values() if str(t["accountId"]) not in seen_ids]
        if to_check:
            extra_online = await _check_targets_concurrently(
                check_session, to_check, extra_live_ids, extra_cache
            )
            for item in extra_online:
                if str(item["accountId"]) not in seen_ids:
                    seen_ids.add(str(item["accountId"]))
                    live.append(item)
        merged_targets = {str(x["accountId"]): x for x in live}
        for t in extra_targets.values():
            merged_targets.setdefault(str(t["accountId"]), t)
        events.emit_sync("live_poll", state="targets", site="onlyfans", targets=list(merged_targets.values()))
        return live

    sig = (all_users, tuple(sorted(username_match.username_keys(usernames))), tuple(sorted(username_match.username_keys(excluded))))
    # a cache with no signature yet holds nothing from another choice of
    # creators, so only a changed signature empties it
    if cache.get("_sig", sig) != sig:
        cache.clear()
    cache["_sig"] = sig

    # Batch subscription path:
    # - ALL with custom filters (--user-list, price/date filters, etc.)
    # - Explicit --username with -fl (--username-list-search)
    list_mode = all_users or search_mode == "list"
    by_name = not list_mode and (
        search_mode == "individual" or len(username_match.username_keys(usernames)) <= _individual_max()
    )
    initial_live = await _update_targets(c, cache, usernames, excluded, all_users, has_filters, by_name)
    targets = cache["targets"]
    extra_cache = None
    extra_initial_live = set()
    extra_targets = {}
    if all_users and has_filters and extra:
        extra_cache = _get_extra_cache(cache, extra, excluded)
        extra_initial_live = await _update_targets(
            c, extra_cache, extra, excluded, False, False, True
        )
        extra_targets = extra_cache.get("targets") or {}

    combined_targets = dict(targets)
    for aid, t in extra_targets.items():
        combined_targets.setdefault(aid, t)

    events.emit_sync("live_poll", state="targets", site="onlyfans", targets=list(combined_targets.values()))
    if not combined_targets:
        return []

    # more creators than LIVE_INDIVIDUAL_MAX: one list scan, not a request per creator
    if list_mode or len(targets) > _individual_max():
        # a failed read fails the poll: it would look like nobody is subscribed
        pages = [page async for page in scrape_subscriptions_active(c, strict=True)]
        live_ids = {s["accountId"] for s in live_subscriptions(pages)} | initial_live | extra_initial_live
        direct = _direct_targets(cache, all_users, targets, pages, live_ids)
        live_ids |= {
            t["accountId"] for t in await _check_targets_concurrently(check_session, direct, set(), cache)
        }
        if extra_targets:
            checked_ids = live_ids | {t["accountId"] for t in direct}
            extra_to_check = [t for t in extra_targets.values() if t["accountId"] not in checked_ids]
            if extra_to_check:
                live_ids |= {
                    t["accountId"]
                    for t in await _check_targets_concurrently(check_session, extra_to_check, set(), extra_cache)
                }
        # the cached target, which keeps the name a renamed creator was looked up as
        return [t for t in combined_targets.values() if t["accountId"] in live_ids]

    # Individual target path (-fi or auto-selected individual search):
    # resolve target accounts once, then poll streams/active concurrently on `checks` (retries=1).
    return await _check_targets_concurrently(check_session, list(combined_targets.values()), initial_live | extra_initial_live, cache)


def recording_path(
    save_location, username: str, when: datetime.datetime | None = None, *, model_id=None
) -> pathlib.Path:
    """``{save_location}/OnlyFans/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live.webm``"""
    import ofscraper.classes.placeholder as placeholder

    when = when or datetime.datetime.now(datetime.timezone.utc)
    return placeholder.live_recording_path(
        save_location, shared.folder_name(username), when,
        site_name="OnlyFans", ext="webm", model_id=model_id,
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
        log.warning("--live-chat only applies to Fansly; OnlyFans recordings have no chat file")
    # a thread: it may start Playwright, whose sync API won't run in this loop
    if not await asyncio.to_thread(live_capture.playwright_ready):
        return
    save_location = common_paths.get_save_location()
    ffmpeg = ffmpeg_finder.get_ffmpeg() or None
    cache_token = _TARGET_CACHE.set({})
    watcher_token = None

    try:
        # Separate sessions: `c` retries batch list calls; `checks` gets one attempt
        # per live status check so a transient failure doesn't stall polling.
        async with manager.Manager.session.aget_ofsession() as c, \
                manager.Manager.session.aget_ofsession(retries=1) as checks:
            loop = asyncio.get_running_loop()
            warned = []
            announced_idle = False
            announced_live_ids = set()
            streaks = {}

            async def fetch_online():
                nonlocal announced_idle, announced_live_ids
                try:
                    online = await get_online_streams(c, checks=checks)
                except Exception as e:
                    shared.warn_streak(streaks, "poll", f"OnlyFans livestream check failed: {e}")
                    log.debug("", exc_info=True)
                    raise

                shared.warn_streak(streaks, "poll")
                w_inc = getattr(watcher, "include_following", None)
                inc = shared.wants_all_usernames(opts["usernames"]) if w_inc is None else bool(w_inc)
                w_extra = getattr(watcher, "extra_usernames", None)
                active_u = None if inc else (opts["usernames"] if w_extra is None else sorted(w_extra))
                w_excl = getattr(watcher, "excluded_usernames", None)
                active_ex = opts["excluded"] if w_excl is None else w_excl
                selected = select_streams(online, active_u, active_ex)
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
                account_id = str(stream["accountId"])
                out = recording_path(save_location, username, model_id=stream["accountId"])
                os.makedirs(os.path.dirname(out), exist_ok=True)
                auth = auth_file.read_auth()
                proxy = _session_proxy(c)
                events.emit_sync(
                    "live_stream",
                    site="onlyfans",
                    account_id=account_id,
                    username=username,
                    status="joining",
                    part_path=out,
                    part_num=1,
                    reason="Launching headless Chromium...",
                )
                try:
                    # capture says when it really starts recording: a page
                    # with nothing to record (a ticketed stream, the login
                    # page) shouldn't announce a recording every poll
                    log.debug(f"Recording OnlyFans livestream for {username} -> {out}")
                    capture_kwargs = dict(
                        username=username,
                        out=out,
                        auth=auth,
                        still_live=lambda: check_live(username),
                        ffmpeg=ffmpeg,
                        proxy=proxy,
                    )
                    if live_capture.capture is _REAL_CAPTURE:
                        capture_kwargs["account_id"] = account_id
                    saved = await record_in_thread(
                        live_capture.capture,
                        stop_event,
                        **capture_kwargs,
                    )
                    (log.info if saved else log.debug)(f"Finished OnlyFans livestream recording for {username}")
                    events.emit_sync(
                        "live_stream",
                        site="onlyfans",
                        account_id=account_id,
                        username=username,
                        status="stopped" if stop_event.is_set() else "ended",
                        part_path=saved or out,
                        part_num=1,
                        reason=(
                            "Saved (stopped by user)"
                            if (saved and stop_event.is_set())
                            else (out.name if saved else "Ended with no recorded data")
                        ),
                    )
                except live_capture.BrowserMissing as e:
                    if not warned:
                        warned.append(True)
                        log.warning(str(e))
                    events.emit_sync(
                        "live_stream",
                        site="onlyfans",
                        account_id=account_id,
                        username=username,
                        status="failed",
                        reason="Playwright Chromium missing",
                    )
                except Exception as e:
                    log.warning(f"{username}: livestream recording failed: {e}")
                    log.debug("", exc_info=True)
                    events.emit_sync(
                        "live_stream",
                        site="onlyfans",
                        account_id=account_id,
                        username=username,
                        status="failed",
                        reason=str(e),
                    )

            if watch:
                log.info(
                    f"Watching for OnlyFans livestreams (interval={opts['interval']}s, max_concurrent={opts['max_concurrent']})..."
                )
            else:
                log.info("Checking for active OnlyFans livestreams...")

            raw_u = opts["usernames"]
            init_names = [raw_u] if isinstance(raw_u, str) else list(raw_u or [])
            watcher = shared.LiveWatcher(
                fetch_online,
                record,
                max_concurrent=opts["max_concurrent"],
                interval=opts["interval"],
                jitter=opts.get("jitter", _jitter()),
                once=not watch,
                site="onlyfans",
                include_following=shared.wants_all_usernames(raw_u),
                extra_usernames=init_names,
                excluded_usernames=opts["excluded"],
            )
            watcher_token = _WATCHER.set(watcher)
            await watcher.run(stop)
    finally:
        if watcher_token is not None:
            _WATCHER.reset(watcher_token)
        _TARGET_CACHE.reset(cache_token)


_REAL_CAPTURE = live_capture.capture
