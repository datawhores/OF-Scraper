import logging

import ofscraper.download.downloadbatch as batchdownloader
import ofscraper.download.downloadnormal as normaldownloader
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.download.utils.log import empty_log
from ofscraper.download.utils.text import textDownloader
from ofscraper.utils.context.run_async import run as run_async
from ofscraper.final.final_user import post_user_process


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
        return batchdownloader.process_dicts(username, model_id, medialist)
    else:
        return await normaldownloader.process_dicts(username, model_id, medialist)


def remove_downloads_with_hashes(username, model_id):
    hash.remove_dupes_hash(username, model_id, "audios")
    hash.remove_dupes_hash(username, model_id, "images")
    hash.remove_dupes_hash(username, model_id, "videos")
