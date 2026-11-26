"""Record OnlyFans livestreams (``--live`` / ``--live-watch``).

Based on the Live Stream Monitor plugin by cjb900 (cjb900/OF-Scraper-GUI).

OnlyFans livestreams are WebRTC (Agora), not an HLS playlist ffmpeg could
read, so a recording is made by the stream page itself: a Chromium browser
(Playwright) opens it with the auth.json login and records the player with
the browser's MediaRecorder (see ``live_capture``).

- **Who is live:** an active subscription with ``hasStream`` set, from the
  same subscriptions list the scraper reads.
- **Still live:** ``users/{username}/streams/active``, asked while recording.

Recordings go to
``{save_location}/OnlyFans/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live.webm``.
The watcher, the Ctrl+C handling and the options are shared with Fansly
(``ofscraper.sites.fansly.live``).
"""

import asyncio
import datetime
import logging
import pathlib
import threading
from urllib.parse import quote

from ofscraper.sites.fansly import live as shared

log = logging.getLogger("shared")

CHECK_TIMEOUT = 15
STREAM_ACTIVE_URL = "https://onlyfans.com/api2/v2/users/{}/streams/active?view=full_with_check"


def recording_path(save_location, username, now=None, *, model_id=None) -> pathlib.Path:
    """``{save_location}/OnlyFans/{username}/Livestreams/{username}_{YYYYMMDD_HHMMSS}_live.webm``"""
    import ofscraper.classes.placeholder as placeholder

    now = now or datetime.datetime.now(tz=datetime.timezone.utc)
    username = shared.folder_name(username)
    return placeholder.live_recording_path(
        save_location, username, now, site_name="OnlyFans", ext="webm", model_id=model_id
    )


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


async def get_online_streams(c) -> list:
    from ofscraper.data.api.subscriptions.subscriptions import scrape_subscriptions_active

    pages = [page async for page in scrape_subscriptions_active(c)]
    return live_subscriptions(pages)


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

    # live checks get one attempt: a failed check counts as "don't know" and
    # the next one comes a minute later, so retries would only hold up the recording
    async with manager.Manager.session.aget_ofsession() as c, \
            manager.Manager.session.aget_ofsession(retries=1) as checks:
        loop = asyncio.get_running_loop()
        warned = []

        async def fetch_online():
            online = await get_online_streams(c)
            return shared.select_streams(online, opts["usernames"], opts["excluded"])

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
                    out=recording_path(save_location, username, model_id=stream["accountId"]),
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
