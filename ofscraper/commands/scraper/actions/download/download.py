import logging
import pathlib
import asyncio

import ofscraper.utils.hash as hash
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.commands.utils.strings import (
    download_activity_str,
)
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.config.data as config_data
import ofscraper.utils.paths.common as common_paths
from ofscraper.utils.string import format_safe

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils


from ofscraper.commands.scraper.actions.utils.paths import setDirectoriesDate

from ofscraper.commands.scraper.actions.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
from ofscraper.commands.scraper.actions.download.run import consumer
from ofscraper.commands.scraper.actions.download.utils.desc import desc
from ofscraper.commands.scraper.actions.download.utils.text import textDownloader
import ofscraper.utils.settings as settings
import ofscraper.managers.manager as manager


async def downloader(username=None, model_id=None, posts=None, media=None, **kwargs):
    download_str = download_activity_str.format(username=username)
    path_str = format_safe(
        f"\nSaving files to [deep_sky_blue2]{str(pathlib.Path(common_paths.get_save_location(),config_data.get_dirformat(),config_data.get_fileformat()))}[/deep_sky_blue2]",
        username=username,
        model_id=model_id,
        model_username=username,
        modelusername=username,
        modelid=model_id,
    )
    with progress_utils.TemporaryTaskState(progress_updater.activity, ["main"]):
        progress_updater.activity.update_task(
            description=download_str + path_str, visible=True
        )
        logging.getLogger("shared").warning(
            download_activity_str.format(username=username)
        )
        values = await download_process(username, model_id, media, posts=posts)
        return values


@run_async
async def download_process(username, model_id, medialist, posts):
    values = await process_dicts(username, model_id, medialist, posts)
    return values


@run
async def process_dicts(username, model_id, medialist, posts):
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
    logging.getLogger("shared").info("Downloading in single thread mode")
    common_globals.mainProcessVariableInit()
    task1 = None
    with progress_utils.setup_live("download"):
        try:

            aws = []
            async with manager.Manager.get_download_session() as c:
                for ele in medialist:
                    aws.append((c, ele, model_id, username))
                task1 = progress_updater.download.add_overall_task(
                    desc.format(
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
                concurrency_limit = get_max_workers()
                lock = asyncio.Lock()
                consumers = [
                    asyncio.create_task(consumer(aws, task1, medialist, lock))
                    for _ in range(concurrency_limit)
                ]
                await asyncio.gather(*consumers)
        except Exception as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        finally:
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


def remove_downloads_with_hashes(username, model_id):
    hash.remove_dupes_hash(username, model_id, "audios")
    hash.remove_dupes_hash(username, model_id, "images")
    hash.remove_dupes_hash(username, model_id, "videos")
