
import platform
import traceback
import ofscraper.actions.utils.globals as common_globals
from ofscraper.actions.utils.log import (
    set_media_log,
)

from ofscraper.actions.actions.metadata.utils.change import change_metadata
from ofscraper.actions.utils.log import get_medialog


platform_name = platform.system()
async def metadata(c, ele, model_id, username):
    try:
        set_media_log(common_globals.log, ele)
        common_globals.attempt.set(0)
        return await change_metadata(c, ele, username, model_id)
    except Exception as e:
        common_globals.log.traceback_(f"{get_medialog(ele)} Metadata Failed\n")
        common_globals.log.traceback_(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        common_globals.log.debug(f"{get_medialog(ele)} exception {e}")
        # we can put into seperate otherqueue_
        return "skipped", 0