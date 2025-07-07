import logging
import traceback

import ofscraper.commands.scraper.actions.utils.log as logs
import ofscraper.utils.text as text
from ofscraper.utils.context.run_async import run
from ofscraper.managers.postcollection import PostCollection


@run
async def textDownloader(values, username=None):
    log = logging.getLogger("shared")
    postcollection=PostCollection()
    try:
        values= (
            [values] if not isinstance(values, list) else values
        )
        postcollection.add_posts(values)
        if not postcollection.posts:
            log.info("No text files found to download")
            return []
        log.info("Downloading Text Files")
        count, fails, exists = await text.get_text(postcollection.posts)
        username = username or "Unknown"
        return [logs.text_log(username, count, fails, exists, log=log)]
    except Exception as E:
        log.debug(f"Issue with text {E}")
        log.debug(f"Issue with text {traceback.format_exc()}")
    return []
