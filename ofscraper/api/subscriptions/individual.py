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
from concurrent.futures import ThreadPoolExecutor

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

import ofscraper.api.profile as profile
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@run
async def get_subscription(accounts=None):
    global sem
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))
    accounts = accounts or read_args.retriveArgs().username
    if not isinstance(accounts, list) and not isinstance(accounts, set):
        accounts = set([accounts])
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        with Progress(
            SpinnerColumn(style=Style(color="blue")), TextColumn("{task.description}")
        ) as progress:
            task1 = progress.add_task(
                f"Getting the following accounts => {accounts} (this may take awhile)..."
            )
            async with sessionbuilder.sessionBuilder() as c:
                out = await get_subscription_helper(c, accounts)
                progress.remove_task(task1)
        outdict = {}
        for ele in filter(lambda x: x["username"] != "modeldeleted", out):
            outdict[ele["id"]] = ele
        log.debug(f"Total subscriptions found {len(outdict.values())}")
        return list(outdict.values())


async def get_subscription_helper(c, accounts):
    out = []
    tasks = [
        asyncio.create_task(profile.scrape_profile_helper_async(c, account))
        for account in accounts
    ]

    new_tasks = []
    while tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for result in done:
            try:
                result = await result
            except Exception as E:
                log.debug(E)
                continue
            out.append(result)
        tasks = list(pending)
        tasks.extend(new_tasks)
        new_tasks = []
    return out
