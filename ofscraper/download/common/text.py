import logging
import traceback

import ofscraper.utils.settings as settings
import ofscraper.utils.text as text
from ofscraper.utils.context.run_async import run


@run
async def textDownloader(objectdicts):
    log = logging.getLogger("shared")
    if objectdicts == None:
        return
    try:
        if not "Text" in settings.get_mediatypes():
            log.info("Skipping Downloading of Text Files")
            return
        log.info("Downloading Text Files")
        data = ({e.postid: e for e in objectdicts}).values()
        await text.get_text(data)
    except Exception as E:
        log.debug(f"Issue with text {E}")
        log.debug(f"Issue with text {traceback.format_exc()}")
