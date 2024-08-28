import logging
import pathlib

import ofscraper.actions.actions.download.batch.downloadbatch as batch
import ofscraper.actions.actions.download.normal.downloadnormal as normal
import ofscraper.utils.constants as constants
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.actions.utils.log import final_log_text
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.runner.close.final.final_user import post_user_script
from ofscraper.commands.utils.strings import (
    download_activity_str,
)
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.config.data as config_data
import ofscraper.utils.paths.common as common_paths
from ofscraper.utils.string import format_safe


async def downloader(username=None,model_id=None, posts=None, media=None, **kwargs):
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
    data, values = await download_process(username,model_id, media, posts=posts)
    return data, values


@run_async
async def download_process(username,model_id, medialist=None, posts=None):
    data, values = await download_picker(username, model_id, medialist, posts)
    post_user_script(username, medialist, posts=None)
    return data, values

@run_async
async def download_model_deleted_process(username,model_id, medialist=None, posts=None):
    data, values = await download_picker(username, model_id, medialist, posts)
    return data, values

async def download_picker(username, model_id, medialist, posts):
    if (
        system.getcpu_count() > 1
        and (
            len(medialist)
            >= settings.get_threads() * constants.getattr("DOWNLOAD_THREAD_MIN")
        )
        and settings.not_solo_thread()
    ):
        return await batch.process_dicts(username, model_id, medialist, posts)
    else:
        return await normal.process_dicts(username, model_id, medialist, posts)


def remove_downloads_with_hashes(username, model_id):
    hash.remove_dupes_hash(username, model_id, "audios")
    hash.remove_dupes_hash(username, model_id, "images")
    hash.remove_dupes_hash(username, model_id, "videos")
