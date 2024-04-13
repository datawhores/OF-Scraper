r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import contextvars
import logging
import traceback

from rich.console import Console

import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
console = Console()


def get_user_list_helper():
    return settings.get_userlist(as_list=True)


def get_black_list_helper():
    return settings.get_blacklist(as_list=True)


async def sort_list(c) -> list:
    attempt.set(0)
    try:
        attempt.set(attempt.get(0) + 1)
        async with c.requests_async(
            constants.getattr("sortSubscription"),
            method="post",
            json={"order": "users.name", "direction": "desc", "type": "all"},
        ) as _:
            pass
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
