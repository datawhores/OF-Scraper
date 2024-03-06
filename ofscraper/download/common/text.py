import logging
import traceback

import ofscraper.utils.settings as settings


def textDownloader(mediadicts):
    log = logging.getLogger("shared")
    try:
        if not "Text" in settings.get_mediatypes():
            log.info("Skipping Downloading of Text Files")
            return
        log.info("Downloading Text Files")
        data = ({e.postid: e for e in mediadicts}).values()
        text.get_text(data)
    except Exception as E:
        log.debug(f"Issue with text {E}")
        log.debug(f"Issue with text {traceback.format_exc()}")
