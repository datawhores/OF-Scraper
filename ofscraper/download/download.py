import json
import logging
import subprocess
import traceback

import ofscraper.download.downloadbatch as batchdownloader
import ofscraper.download.downloadnormal as normaldownloader
import ofscraper.filters.media.helpers as helpers
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
import ofscraper.utils.hash as hash
import ofscraper.utils.separate as seperate
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded,
    get_media_ids_downloaded_model,
)
from ofscraper.download.shared.utils.text import textDownloader


def medialist_filter(medialist, model_id, username):
    log = logging.getLogger("shared")
    medialist = seperate.seperate_by_self(medialist)

    if read_args.retriveArgs().force_all:
        log.info("forcing all")
    elif read_args.retriveArgs().force_model_unique:
        log.info("Downloading unique medi afor model")
        media_ids = set(
            get_media_ids_downloaded_model(model_id=model_id, username=username)
        )
        log.debug(
            f"Number of unique media ids in database for {username}: {len(media_ids)}"
        )
        medialist = seperate.separate_by_id(medialist, media_ids)
        log.debug(f"Number of new mediaids with dupe ids removed: {len(medialist)}")
        medialist = seperate.seperate_avatars(medialist)
        log.debug("Removed previously downloaded avatars/headers")
        log.debug(f"Final Number of media to download {len(medialist)}")
    else:
        log.info("Downloading unique media across all models")
        media_ids = set(get_media_ids_downloaded(model_id=model_id, username=username))
        log.debug("Number of unique media ids in database for all models")
        medialist = seperate.separate_by_id(medialist, media_ids)
        log.debug(f"Number of new mediaids with dupe ids removed: {len(medialist)}")
        medialist = seperate.seperate_avatars(medialist)
        log.debug("Removed previously downloaded avatars/headers")
        log.debug(f"Final Number of media to download {len(medialist)} ")

    return medialist


def download_process(username, model_id, medialist, posts=None):
    data = None
    if read_args.retriveArgs().metadata:
        medialist = (
            list(filter(lambda x: x.canview, medialist))
            if constants.getattr("REMOVE_UNVIEWABLE_METADATA")
            else medialist
        )
        logging.getLogger().info(f"Final media count for metadata {len(medialist)}")
        medialist = medialist_filter(medialist, model_id, username)
        medialist = helpers.ele_count_filter(medialist)
        data = download_picker(username, model_id, medialist)
    else:
        medialist = list(filter(lambda x: x.canview, medialist))
        medialist = medialist_filter(medialist, model_id, username)
        medialist = helpers.ele_count_filter(medialist)
        logging.getLogger().info(f"Final media count for download {len(medialist)}")
        textDownloader(posts, username=username)
        data = download_picker(username, model_id, medialist)
        remove_downloads_with_hashes(username, model_id)
    download_post_process(username, model_id, medialist, posts)
    return data


def download_picker(username, model_id, medialist):
    if len(medialist) == 0:
        logging.getLogger("shared").error(
            f"[bold]{username}[/bold] ({0} photos, {0} videos, {0} audios,  {0} skipped, {0} failed)"
        )
        return 0, 0, 0, 0, 0
    elif (
        system.getcpu_count() > 1
        and (
            len(medialist)
            >= config_data.get_threads() * constants.getattr("DOWNLOAD_THREAD_MIN")
        )
        and settings.not_solo_thread()
    ):
        return batchdownloader.process_dicts(username, model_id, medialist)
    else:
        return normaldownloader.process_dicts(username, model_id, medialist)


def remove_downloads_with_hashes(username, model_id):
    hash.remove_dupes_hash(username, model_id, "audios")
    hash.remove_dupes_hash(username, model_id, "images")
    hash.remove_dupes_hash(username, model_id, "videos")


def download_post_process(username, model_id, medialist, postlist):
    log = logging.getLogger("shared")
    if not settings.get_post_download_script():
        return
    try:
        mediadump = json.dumps(list(map(lambda x: x.media, medialist)))
        postdump = json.dumps(list(map(lambda x: x.post, postlist)))
        model_id = str(model_id)
        subprocess.run(
            [
                settings.get_post_download_script(),
                username,
                model_id,
                mediadump,
                postdump,
            ]
        )
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
