
import platform
import traceback
import ofscraper.actions.download.utils.globals as common_globals
from ofscraper.actions.download.utils.log import (
    set_media_log,
)

from ofscraper.actions.metadata.utils.change import change_metadata
from ofscraper.actions.download.utils.log import get_medialog
from ofscraper.classes.download_retries import download_retry


platform_name = platform.system()
async def metadata(c, ele, model_id, username):
    # set logs for mpd
    try:
        set_media_log(common_globals.log, ele)
        common_globals.attempt.set(0)
        async for _ in download_retry():
            return await change_metadata(c, ele, username, model_id)
    except Exception as e:
        common_globals.log.traceback_(f"{get_medialog(ele)} Metadata Failed\n")
        common_globals.log.traceback_(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        common_globals.log.debug(f"{get_medialog(ele)} exception {e}")
        # we can put into seperate otherqueue_
        return "skipped", 0