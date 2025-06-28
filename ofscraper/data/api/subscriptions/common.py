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

import asyncio
import logging
import traceback

from rich.console import Console

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")
console = Console()


def get_user_list_helper():
    return settings.get_settings().userlist


def get_black_list_helper():
    return settings.get_settings().blacklist


async def sort_list(c) -> list:
    url = of_env.getattr("sortSubscriptions")
    try:
        async with c.requests_async(
            method="post",
            json={"order": "users.name", "direction": "desc", "type": "all"},
        ) as _:
            pass
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
