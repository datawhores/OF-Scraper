import asyncio
import logging
import pathlib
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.managers.manager as manager
import ofscraper.sites as sites
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.config.data as config_data
import ofscraper.utils.dry_run as dry_run
import ofscraper.utils.hash as hash
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.commands.scraper.actions.download.managers.fansly_stream_download import (
    FanslyStreamDownloadManager,
)
from ofscraper.commands.scraper.actions.download.run import consumer, download
from ofscraper.commands.scraper.actions.download.utils import silent
from ofscraper.commands.scraper.actions.download.utils.desc import desc
from ofscraper.commands.scraper.actions.download.utils.refresh import (
    fansly_refresher,
)
from ofscraper.commands.scraper.actions.download.utils.text import textDownloader
from ofscraper.commands.scraper.actions.utils.paths import setDirectoriesDate
from ofscraper.commands.scraper.actions.utils.workers import get_max_workers
from ofscraper.commands.utils.strings import (
    download_activity_str,
)
from ofscraper.db.operations_.media import prev_download_media_data
from ofscraper.utils.context.run_async import run
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.utils.markup import escape_text
from ofscraper.utils.string import format_safe


def save_path_str(username=None, model_id=None):
    """The "Saving files to ..." progress line. The path is filled in first
    and escaped after, so brackets in it or in the filled-in names show as
    they are."""
    # the site's media root: <save location>/Fansly on Fansly runs, unless the
    # templates name the site with {site_name}
    path = format_safe(
        str(
            pathlib.Path(
                placeholder.default_media_root(),
                config_data.get_dirformat(),
                config_data.get_fileformat(),
            )
        ),
        username=username,
        model_id=model_id,
        model_username=username,
        modelusername=username,
        modelid=model_id,
        site_name=sites.site_name(),
        sitename=sites.site_name(),
    )
    # a type_options entry sends some files elsewhere; the line says so
    # instead of listing each template
    from ofscraper.utils.config.naming_check import LIVE_TYPE_KEYS, type_name

    others = ", ".join(sorted(
        name for name, entry in config_data.get_type_options().items()
        if entry and type_name(name) not in LIVE_TYPE_KEYS
    ))
    also = f" ({escape_text(others)}: as type_options sets)" if others else ""
    return f"\nSaving files to [deep_sky_blue2]{escape_text(path)}[/deep_sky_blue2]{also}"


async def downloader(username=None, model_id=None, posts=None, media=None, **kwargs):
    download_str = download_activity_str.format(username=username)
    path_str = save_path_str(username=username, model_id=model_id)
    with progress_utils.TemporaryTaskState(progress_updater.activity, ["main"]):
        progress_updater.activity.update_task(
            description=download_str + path_str, visible=True
        )
        logging.getLogger("shared").warning(
            download_activity_str.format(username=username)
        )
        values = await download_process(username, model_id, media, posts=posts)
        if dry_run.active():
            return values
        if sites.is_fansly() and not stop.requested.is_set():
            await recheck_silent(username, model_id, kwargs.get("all_media") or media)
        return values


async def _download_again(c, ele, model_id=None, username=None):
    """True: saved again with sound; REFUSED: the new copy still has none;
    NOT_KEPT: it has sound but wasn't kept (a filter skipped it, or the
    silent file could not be replaced); False: the download failed (network,
    disk), which uses no check."""
    ele.still_silent = False
    ele.not_kept = None
    try:
        media_type, _ = await download(c, ele, model_id, username)
    finally:
        # a size limit swaps the item's type for the download, and no
        # download loop ends this one. The item gets its type back here, so
        # the stats still count the video this run saved
        restore = getattr(ele, "update_download_status", None)
        if restore:
            restore()
    if str(media_type).lower() == "videos":
        return True
    if getattr(ele, "still_silent", False):
        return silent.REFUSED
    if getattr(ele, "not_kept", None):
        logging.getLogger("shared").info(
            f"Media {ele.id}: {ele.not_kept}; the video without sound stays as it is"
        )
        return silent.NOT_KEPT
    return False


async def _saved_path(ele, model_id=None, username=None):
    """The file the database has for ``ele``, or None."""
    row = await prev_download_media_data(ele, model_id=model_id, username=username)
    if row and row.get("directory") and row.get("filename"):
        return pathlib.Path(row["directory"], row["filename"])
    return None


@run
async def recheck_silent(username, model_id, all_media):
    """Check the audio of the creator's videos saved without sound (see
    ``silent.recheck``), after the run's downloads."""
    if settings.get_settings().text_only or not silent.flags(model_id):
        return
    common_globals.mainProcessVariableInit()
    try:
        async with manager.Manager.session.get_download_session() as c:
            await silent.recheck(
                c,
                username,
                model_id,
                {str(m.id): m for m in all_media or []},
                FanslyStreamDownloadManager().audio_check,
                partial(_download_again, model_id=model_id, username=username),
                partial(_saved_path, model_id=model_id, username=username),
            )
    except Exception as E:
        logging.getLogger("shared").debug(f"Fansly: checking silent videos failed: {E}")
    finally:
        await asyncio.get_event_loop().run_in_executor(common_globals.thread, cache.close)
        common_globals.thread.shutdown()


@run_async
async def download_process(username, model_id, medialist, posts):
    if dry_run.active():
        # no text files, no downloads, no duplicate removal: count only
        await dry_run.record(username, [] if settings.get_settings().text_only else medialist)
        return (0, 0, 0, 0, 0)
    values = await process_dicts(username, model_id, medialist, posts)
    # off the event loop: it hashes the files it is about to delete
    await asyncio.to_thread(remove_downloads_with_hashes, username, model_id)
    return values


@run
async def process_dicts(username, model_id, medialist, posts, on_result=None):
    """Return batch totals; optionally call on_result(media, result) per file.

    Results are "downloaded", "skipped" (intentional), "failed", or "stopped".
    The callback runs in the download worker as each file finishes.
    """
    # 2. Handle text download if enabled
    if not isinstance(medialist, list):
        medialist = [medialist]
    if not isinstance(posts, list):
        posts = [posts]
    if settings.get_settings().text:
        await textDownloader(posts, username=username)
    if settings.get_settings().text_only:
        return (0, 0, 0, 0, 0)
    medialist_empty = len(medialist) == 0

    if medialist_empty:
        return (0, 0, 0, 0, 0)

    # Continue to download process
    for ele in medialist:
        ele.download_unstarted = True
        ele.download_stopped = False
    if stop.requested.is_set():
        return (0, 0, 0, 0, 0)
    concurrency_limit = get_max_workers()
    logging.getLogger("shared").info(
        f"Downloading up to {concurrency_limit} "
        f"{'file' if concurrency_limit == 1 else 'files'} at a time"
    )
    common_globals.mainProcessVariableInit()
    # the consumers take items from the end of the list
    fansly_refresher.reset()
    fansly_refresher.expect(reversed(medialist))
    task1 = None
    with progress_utils.setup_live("download"):
        try:

            aws = []
            async with manager.Manager.session.get_download_session() as c:
                for ele in medialist:
                    aws.append((c, ele, model_id, username))
                task1 = progress_updater.download.add_overall_task(
                    desc.format(
                        stopped=0,
                        p_count=0,
                        v_count=0,
                        a_count=0,
                        skipped=0,
                        mediacount=len(medialist),
                        forced_skipped=0,
                        sumcount=0,
                        total_bytes_download=0,
                        total_bytes=0,
                    ),
                    total=len(aws),
                    visible=True,
                )
                lock = asyncio.Lock()
                consumers = [
                    asyncio.create_task(consumer(aws, task1, medialist, lock, on_result=on_result))
                    for _ in range(concurrency_limit)
                ]
                try:
                    await asyncio.gather(*consumers)
                finally:
                    for task in consumers:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*consumers, return_exceptions=True)
        finally:
            fansly_refresher.reset()
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread, cache.close
            )
            common_globals.thread.shutdown()

        setDirectoriesDate()
        progress_updater.download.remove_overall_task(task1)
        return (
            common_globals.video_count,
            common_globals.audio_count,
            common_globals.photo_count,
            common_globals.forced_skipped,
            common_globals.skipped,
        )


# the media types whose duplicate files remove_hash_match removes, as the
# database stores them
HASH_MEDIA_TYPES = ("Audios", "Images", "Videos")


def remove_downloads_with_hashes(username, model_id):
    """After a creator's downloads, with remove_hash_match on: delete the
    later copies of files the creator already has. Returns the paths
    deleted. Nothing is deleted once a stop is asked for (a stopped run may
    have left a file unfinished), or in a run that only saves text."""
    if settings.get_settings().text_only:
        return []
    removed = hash.remove_dupes_hash(
        username, model_id, HASH_MEDIA_TYPES, stopped=stop.requested.is_set
    )
    if removed:
        logging.getLogger("shared").warning(
            f"Removed {len(removed)} duplicate "
            f"{'file' if len(removed) == 1 else 'files'} of {username}"
        )
    return removed
