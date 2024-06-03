import logging
import traceback

import ofscraper.classes.media as media_class
import ofscraper.download.shared.log as logs
import ofscraper.utils.settings as settings
import ofscraper.utils.text as text
from ofscraper.utils.context.run_async import run


@run
async def textDownloader(objectdicts, username=None):
    log = logging.getLogger("shared")
    if not bool(objectdicts):
        return
    try:
        if "Text" not in settings.get_mediatypes():
            log.info("Skipping Downloading of Text Files")
            return
        objectdicts = (
            [objectdicts] if not isinstance(objectdicts, list) else objectdicts
        )
        log.info("Downloading Text Files")
        data = (
            {
                e.postid if isinstance(e, media_class.Media) else e.id: e
                for e in objectdicts
            }
        ).values()
        count, fails, exists = await text.get_text(data)
        username or "Unknown"
        logs.text_log(username, count, fails, exists, log=log)
    except Exception as E:
        log.debug(f"Issue with text {E}")
        log.debug(f"Issue with text {traceback.format_exc()}")
