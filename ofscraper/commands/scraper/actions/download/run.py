r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import asyncio
import pathlib
import re
import traceback
import urllib.parse
from contextlib import nullcontext

from ofscraper.commands.scraper.actions.download import stop

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.events as events
import ofscraper.utils.live.updater as progress_updater
from ofscraper.utils.logs.classes.classes import SensitiveFormatter
from ofscraper.commands.scraper.actions.utils.log import (
    log_download_progress,
)
from ofscraper.commands.scraper.actions.utils.log import get_medialog

from ofscraper.commands.scraper.actions.utils.progress.convert import convert_num_bytes
from ofscraper.commands.scraper.actions.download.utils.desc import desc
from ofscraper.commands.scraper.actions.download.managers.alt_download import (
    AltDownloadManager,
)
from ofscraper.commands.scraper.actions.download.managers.main_download import (
    MainDownloadManager,
)
from ofscraper.commands.scraper.actions.download.managers.fansly_stream_download import (
    FanslyStreamDownloadManager,
)
from ofscraper.commands.scraper.actions.download.utils.refresh import (
    fansly_refresher,
    fresh_before_download,
)
from ofscraper.classes.of.media import Media
from ofscraper.sites.fansly import video as fansly_video
from ofscraper.commands.scraper.actions.download.utils import silent


async def consumer(aws, task1, medialist, lock, on_result=None):
    while True:
        async with lock:
            if stop.requested.is_set() or not aws:
                break
            data = aws.pop()
        if data is None:
            break
        if not await handle_one(data, task1, lambda: len(medialist), on_result):
            break


async def handle_one(data, task1, total, on_result=None):
    """Download one item and count its result.

    ``data`` is ``(c, ele, model_id, username)``; ``total`` returns the count
    shown as the run's media count. Returns False when a stop request ended
    the item before it started, so the caller takes no more items.
    """
    ele = None
    error = None
    try:
        ele: Media = data[1]
        ele.download_stopped = False
        ele.download_unstarted = False
        # the saved file's path, set when item_downloaded is sent
        ele.download_saved = None
        # Stream videos retain their existing cancellation behavior.
        context = nullcontext() if fansly_video.uses_stream(ele) else stop.transfer(ele)
        with context:
            pack = await download(*data)
        common_globals.log.debug(f"unpack {pack} count {len(pack)}")
        media_type, num_bytes_downloaded = pack
    except asyncio.CancelledError:
        if not stop.requested.is_set():
            raise
        if not getattr(ele, "download_started", False):
            ele.download_unstarted = True
            return False
        if getattr(ele, "download_saved", None) is not None:
            # stopped in after_download_script: the file is saved and
            # recorded, and item_downloaded was sent
            media_type = ele.mediatype
            num_bytes_downloaded = _saved_size(ele.download_saved)
        else:
            ele.download_stopped = True
            media_type = "stopped"
            num_bytes_downloaded = 0
    except Exception as e:
        common_globals.log.info(
            f"{get_medialog(ele)} Download Failed because\n{e}"
        )
        common_globals.log.traceback_(traceback.format_exc())
        media_type = "skipped"
        num_bytes_downloaded = 0
        error = _failure_reason(e)
    # finished: never fetched new links for again
    fansly_refresher.done(ele)
    try:
        common_globals.total_bytes_downloaded = (
            common_globals.total_bytes_downloaded + num_bytes_downloaded
        )
        media_type = media_type.lower()
        if media_type == "images":
            common_globals.photo_count += 1
            ele.mark_download_succeeded()

        elif media_type == "videos":
            common_globals.video_count += 1
            ele.mark_download_succeeded()
        elif media_type == "audios":
            common_globals.audio_count += 1
            ele.mark_download_succeeded()
        elif media_type == "stopped":
            common_globals.stopped += 1
        elif media_type == "skipped":
            common_globals.skipped += 1
            ele.mark_download_failed()
        elif media_type == "forced_skipped":
            ele.mark_download_skipped()
            common_globals.forced_skipped += 1
        result = (
            "stopped" if media_type == "stopped"
            else "failed" if media_type == "skipped"
            else "skipped" if media_type == "forced_skipped"
            else "downloaded"
        )
        if on_result is not None:
            on_result(ele, result)
        await events.emit(
            "item_finished", ele=ele, username=data[3], result=result,
            reason=_reason(ele, result, error),
        )
        sum_count = (
            common_globals.photo_count
            + common_globals.video_count
            + common_globals.audio_count
            + common_globals.skipped
            + common_globals.forced_skipped
            + common_globals.stopped
        )
        log_download_progress(media_type)
        progress_updater.download.update_overall_task(
            task1,
            description=desc.format(
                stopped=common_globals.stopped,
                p_count=common_globals.photo_count,
                v_count=common_globals.video_count,
                a_count=common_globals.audio_count,
                skipped=common_globals.skipped,
                forced_skipped=common_globals.forced_skipped,
                mediacount=total(),
                sumcount=sum_count,
                total_bytes=convert_num_bytes(common_globals.total_bytes),
                total_bytes_download=convert_num_bytes(
                    common_globals.total_bytes_downloaded
                ),
            ),
            refresh=True,
            advance=1,
        )
        if not stop.requested.is_set():
            await asyncio.sleep(1)
    except Exception as e:
        common_globals.log.info(
            f"{get_medialog(ele)} Download Failed because\n{e}"
        )
        common_globals.log.traceback_(traceback.format_exc())
    return True


def _saved_size(path):
    try:
        return pathlib.Path(path).stat().st_size
    except OSError:
        # the after-download script may have moved it
        return 0


# a link with a scheme or starting with //; it ends at a quote, a space or a
# backslash (JSON's \" or a Windows path after it)
_URL = re.compile(r"(?:\b[a-zA-Z][a-zA-Z0-9+.-]*:)?//[^\s'\"<>\\]+")
# a query string, with or without the link before it: a ? and then text with
# an = in it
_QUERY = re.compile(r"\?(?=[^\s'\"<>\\]*=)[^\s'\"<>\\]*")


def _error_text(error):
    """str(error), but an OSError's path as it is, not repr'd: str() shows a
    Windows path with doubled backslashes."""
    if isinstance(error, OSError) and error.filename is not None:
        code = (
            f"WinError {error.winerror}" if getattr(error, "winerror", None)
            else f"Errno {error.errno}"
        )
        text = f"[{code}] {error.strerror}: {error.filename}"
        if error.filename2 is not None:
            text += f" -> {error.filename2}"
        return text
    return str(error)


def _failure_reason(error):
    """An error's text for item_finished: on one line, with no link (a signed
    link is a key to the file), and hidden as the logs hide cookies, IDs and
    the home folder's name. A link is found in its JSON-escaped (https:\\/\\/)
    and percent-encoded forms too; a link without a scheme keeps its address
    but loses everything after the ?."""
    text = _error_text(error).replace("\\/", "/")
    # percent-encoded, perhaps more than once; each pass that changes the
    # text shortens it, so this ends
    while (decoded := urllib.parse.unquote(text)) != text:
        text = decoded
    text = _QUERY.sub("", _URL.sub("{url}", text))
    text = " ".join(text.split())
    return SensitiveFormatter()._filter(text) or type(error).__name__


def _skip_reason(ele):
    """Why a downloader skipped an item, when it didn't say."""
    if any(ele.skip_script_answers.values()):
        return "skip_download_script"
    if ele.mediatype == "Forced_skipped":
        return "size limit"
    return "skipped"


def _reason(ele, result, error=None):
    """item_finished's reason: None for a downloaded or stopped item."""
    if result in ("downloaded", "stopped"):
        return None
    return (
        error
        or getattr(ele, "download_reason", None)
        or ("download failed" if result == "failed" else "skipped")
    )


async def _clear_silent_flag(model_id, ele):
    """Drop the "saved without sound" flag of a Fansly video (silent.py)."""
    try:
        await asyncio.get_running_loop().run_in_executor(
            common_globals.thread, silent.clear, model_id, ele.id
        )
    except Exception as E:
        common_globals.log.debug(
            f"{get_medialog(ele)} could not record that it has sound: {type(E).__name__}"
        )


async def download(c, ele, model_id, username):
    try:
        data = None
        # skip_download_script's answers last for this download call and its
        # retries: the check table sends the same Media again, and it's
        # asked again then, as before (#350)
        ele.skip_script_answers = {}
        # why the item failed or was skipped, for item_finished; a
        # downloader that knows better sets it first
        ele.download_reason = None
        # a link signed for an address range the CDN now refuses gets a new
        # one first, usually fetched already for an earlier refusal
        await fresh_before_download(ele)
        if fansly_video.uses_stream(ele):
            # None: the stream can't be used and the item has a direct file
            data = await FanslyStreamDownloadManager().stream_download(
                c, ele, username, model_id
            )
        if data is None and ele.url:
            data = await MainDownloadManager().main_download(
                c,
                ele,
                username,
                model_id,
            )
            if fansly_video.uses_stream(ele) and data and str(data[0]).lower() == "videos":
                # saved from its direct file, which has the sound: a copy
                # flagged as saved without sound needs no more checks
                await _clear_silent_flag(model_id, ele)
        elif data is None and ele.mpd:
            data = await AltDownloadManager().alt_download(c, ele, username, model_id)
        if data is None:
            # nothing to fetch: locked media, sent from the check table, has
            # no link; a run's own filters leave it out
            common_globals.log.info(
                f"{get_medialog(ele)} Not downloaded: it has no link (locked or removed)"
            )
            ele.download_reason = "no link"
            return "skipped", 0
        if str(data[0]).lower() == "forced_skipped" and not ele.download_reason:
            # read now: the loop gives a size-skipped item its type back
            ele.download_reason = _skip_reason(ele)
        common_globals.log.debug(f"{get_medialog(ele)} Download finished")
        return data
    except Exception as E:
        common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
        common_globals.log.debug(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        ele.download_reason = _failure_reason(E)
        return "skipped", 0
