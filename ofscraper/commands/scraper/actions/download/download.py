import logging
import pathlib
import asyncio

import ofscraper.utils.hash as hash
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.scripts.after_download_action_script import after_download_action_script
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

from ofscraper.commands.scraper.actions.utils.log import final_log, final_log_text

from ofscraper.commands.scraper.actions.utils.paths import setDirectoriesDate

from ofscraper.commands.scraper.actions.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
from ofscraper.commands.scraper.actions.download.run import consumer
from ofscraper.commands.scraper.actions.download.utils.desc import desc
from ofscraper.commands.scraper.actions.download.utils.text import textDownloader
from ofscraper.utils.args.accessors.areas import get_download_area
import ofscraper.utils.settings as settings
import ofscraper.main.manager as manager
from ofscraper.commands.scraper.actions.utils.log import final_log, final_log_text


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

    progress_updater.update_activity_task(description=download_str + path_str)
    logging.getLogger("shared").warning(download_activity_str.format(username=username))
    progress_updater.update_activity_task(description="")
    data, values = await download_process(username, model_id, media, posts=posts)
    return data, values


@run_async
async def download_process(username, model_id, medialist, posts):
    data, values = await process_dicts(username, model_id, medialist, posts)
    after_download_action_script(username, medialist)
    return data, values


@run_async
async def download_model_deleted_process(
    username, model_id, medialist=None, posts=None
):
    data, values = await process_dicts(username, model_id, medialist, posts)
    return data, values


@run
async def process_dicts(username, model_id, medialist, posts):
    log_text_array = []
    log_text_array.append(await textDownloader(posts, username=username))
    logging.getLogger("shared").info("Downloading in single thread mode")
    common_globals.mainProcessVariableInit()
    if settings.get_settings().text_only:
        return log_text_array, (0, 0, 0, 0, 0)
    elif settings.get_settings().command in {
        "manual",
        "post_check",
        "msg_check",
        "story_check",
        "paid_check",
    }:
        pass
    elif settings.get_settings().scrape_paid:
        pass
    elif len(get_download_area()) == 0:
        empty_log = final_log_text(username, 0, 0, 0, 0, 0, 0)
        logging.getLogger("shared").error(empty_log)
        log_text_array.append(empty_log)
        return log_text_array, (0, 0, 0, 0, 0)

    if len(medialist) == 0:
        empty_log = final_log_text(username, 0, 0, 0, 0, 0, 0)
        logging.getLogger("shared").error(empty_log)
        log_text_array.append(empty_log)
        return log_text_array, (0, 0, 0, 0, 0)
    task1 = None
    with progress_utils.setup_download_progress_live():
        try:

            aws = []
            async with manager.Manager.get_download_session() as c:
                for ele in medialist:
                    aws.append((c, ele, model_id, username))
                task1 = progress_updater.add_download_task(
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
        final_log(username, log=logging.getLogger("shared"))
        progress_updater.remove_download_task(task1)
        log_text_array.append(final_log_text(username))
        return log_text_array, (
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
