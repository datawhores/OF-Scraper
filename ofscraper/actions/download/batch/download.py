
import platform
import traceback

import ofscraper.actions.download.utils.globals as common_globals
import ofscraper.utils.args.accessors.read as read_args
from ofscraper.actions.download.batch.alt_downloadbatch import alt_download
from ofscraper.actions.download.batch.main_downloadbatch import main_download
from ofscraper.actions.download.utils.log import (
    set_media_log,
)
from ofscraper.actions.download.utils.log import get_medialog

from ofscraper.actions.download.utils.metadata import metadata



platform_name = platform.system()
async def download(c, ele, model_id, username):
    # set logs for mpd
    set_media_log(common_globals.log, ele)
    common_globals.attempt.set(0)
    try:
        if read_args.retriveArgs().metadata:
            return await metadata(c, ele, username, model_id)
        #conditions for download
        if ele.url:
            data=await main_download(c, ele, username, model_id)
        elif ele.mpd:
            data=await alt_download(c, ele, username, model_id)
        common_globals.log.debug(f"{get_medialog(ele)} Download finished")
        return data
    except Exception as e:
        common_globals.log.traceback_(f"{get_medialog(ele)} Download Failed\n{e}")
        common_globals.log.traceback_(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        # we can put into seperate otherqueue_
        return "skipped", 0