import logging

import ofscraper.db.operations as operations
import ofscraper.download.downloadbatch as batchdownloader
import ofscraper.download.downloadnormal as normaldownloader
import ofscraper.filters.media.helpers as helpers
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
import ofscraper.utils.separate as seperate
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system


def medialist_filter(medialist, model_id, username):
    log = logging.getLogger("shared")
    if not read_args.retriveArgs().dupe:
        media_ids = set(
            operations.get_media_ids_downloaded(model_id=model_id, username=username)
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
        log.info(f"forcing all downloads media count {len(medialist)}")
    return medialist


def download_picker(username, model_id, medialist):
    medialist = medialist_filter(medialist, model_id, username)
    medialist = helpers.post_count_filter(medialist)
    if len(medialist) == 0:
        logging.getLogger("shared").error(
            f"[bold]{username}[/bold] ({0} photos, {0} videos, {0} audios,  {0} skipped, {0} failed)"
        )
        return 0, 0, 0, 0, 0
    elif (
        system.getcpu_count() > 1
        and (
            len(medialist)
            >= config_data.get_download_semaphores()
            * constants.getattr("DOWNLOAD_THREAD_MIN")
        )
        and settings.not_solo_thread()
    ):
        return batchdownloader.process_dicts(username, model_id, medialist)
    else:
        return normaldownloader.process_dicts(username, model_id, medialist)
