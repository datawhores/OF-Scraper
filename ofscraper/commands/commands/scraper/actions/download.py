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
import ofscraper.utils.constants as constants
from ofscraper.content.scrape_paid import (
    process_scrape_paid,
    process_user,
    process_user_info_printer,
)
from ofscraper.commands.utils.strings import (
    all_paid_download_str,
    all_paid_progress_download_str,
    download_activity_str,
)
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")





def unique_name_warning():
    if not placeholder.check_uniquename():
        log.warning(
            "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
        )
        time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)


@run
async def scrape_paid_all():
    out = ["[bold yellow]Scrape Paid Results[/bold yellow]"]

    async for count, value, length in process_scrape_paid():
        process_user_info_printer(
            value,
            length,
            count,
            all_paid_update=all_paid_download_str,
            all_paid_activity=download_activity_str,
            log_progress=all_paid_progress_download_str,
        )
        out.append(await process_user(value, length))
    return out
