import logging
import pathlib

import ofscraper.actions.actions.download.batch.downloadbatch as batch
import ofscraper.actions.actions.download.normal.downloadnormal as normal
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.actions.utils.log import empty_log
from ofscraper.actions.actions.download.utils.text import textDownloader
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.runner.close.final.final_user import post_user_process
from ofscraper.commands.utils.strings import (
    download_activity_str,
)
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.config.data as config_data
import ofscraper.utils.paths.common as common_paths
from ofscraper.utils.string import format_safe


async def downloader(ele=None, posts=None, media=None, **kwargs):
    model_id = ele.id
    username = ele.name
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
    logging.getLogger("shared_other").warning(
        download_activity_str.format(username=username)
    )
    progress_updater.update_activity_task(description="")
    return await download_process(username, model_id, media, posts=posts)

@run_async
async def download_process(username, model_id, medialist, posts=None):
    if not read_args.retriveArgs().command == "metadata":
        await textDownloader(posts, username=username)
    data = await download_picker(username, model_id, medialist)
    post_user_process(username, model_id, medialist, posts)
    return data


async def download_picker(username, model_id, medialist):
    if len(medialist) == 0:
        out = empty_log(username)
        logging.getLogger("shared").error(out)
        return out
    elif (
        system.getcpu_count() > 1
        and (
            len(medialist)
            >= settings.get_threads() * constants.getattr("DOWNLOAD_THREAD_MIN")
        )
        and settings.not_solo_thread()
    ):
        return batch.process_dicts(username, model_id, medialist)
    else:
        return await normal.process_dicts(username, model_id, medialist)


def remove_downloads_with_hashes(username, model_id):
    hash.remove_dupes_hash(username, model_id, "audios")
    hash.remove_dupes_hash(username, model_id, "images")
    hash.remove_dupes_hash(username, model_id, "videos")
