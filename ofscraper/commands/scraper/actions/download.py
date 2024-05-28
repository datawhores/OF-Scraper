r"""_____  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
"""

import logging
import time

import ofscraper.classes.placeholder as placeholder
import ofscraper.download.download as download
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.helpers.strings import  download_str,all_paid_progress_download_str
from ofscraper.commands.helpers.scrape_paid import process_scrape_paid

log = logging.getLogger("shared")


async def downloader(ele=None, posts=None, media=None, **kwargs):
    model_id = ele.id
    username = ele.name
    progress_utils.update_activity_task(description=download_str.format(name=username))
    logging.getLogger("shared_other").warning(download_str.format(name=username))
    return await download.download_process(username, model_id, media, posts=posts)





def unique_name_warning():
    if not placeholder.check_uniquename():
        log.warning(
            "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
        )
        time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)


def scrape_paid_all():
    progress_utils.update_activity_task(description="Downloading Paid Content")
    return process_scrape_paid(download_progress_message=download_str,log_progress_message=all_paid_progress_download_str)
