import logging
import traceback

import ofscraper.utils.text as text
from ofscraper.utils.context.run_async import run
from ofscraper.managers.postcollection import PostCollection
import ofscraper.managers.manager as manager


@run
async def textDownloader(values, username=None):
    log = logging.getLogger("shared")
    postcollection = PostCollection()
    posts = None
    try:
        values = [values] if not isinstance(values, list) else values
        postcollection.add_posts(values)
        posts = postcollection.posts
        if not posts:
            log.info("No text files found to download")
            return []
        log.info("Downloading Text Files")
        await text.get_text(username, posts)
    except Exception as E:
        log.debug(f"Issue with text {E}")
        log.debug(f"Issue with text {traceback.format_exc()}")
    manager.Manager.stats_manager.update_and_print_stats(username, "text", posts)
    return []
