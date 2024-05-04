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
from concurrent.futures import ThreadPoolExecutor

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

import ofscraper.api.profile as profile
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@run
async def get_subscription(accounts=None):
    accounts = accounts or read_args.retriveArgs().usernames
    if not isinstance(accounts, list) and not isinstance(accounts, set):
        accounts = set([accounts])
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        with Progress(
            SpinnerColumn(style=Style(color="blue")), TextColumn("{task.description}")
        ) as job_progress:
            task1 = job_progress.add_task(
                f"Getting the following accounts => {accounts} (this may take awhile)..."
            )
            async with sessionManager.sessionManager(
                sem=constants.getattr("SUBSCRIPTION_SEMS"),
                retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
                new_request_auth=True,
            ) as c:
                out = await get_subscription_helper(c, accounts)
                job_progress.remove_task(task1)
        outdict = {}
        for ele in filter(
            lambda x: x["username"] != constants.getattr("DELETED_MODEL_PLACEHOLDER"),
            out,
        ):
            outdict[ele["id"]] = ele
        log.debug(f"Total subscriptions found {len(outdict.values())}")
        return list(outdict.values())


async def get_subscription_helper(c, accounts):
    output = []
    tasks = [
        asyncio.create_task(profile.scrape_profile_helper_async(c, account))
        for account in accounts
    ]
    for task in asyncio.as_completed(tasks):
        try:
            result = await task
            log.debug(f"subscription data found for {result['username']} ")
            log.trace(result)
            output.append(result)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            continue
    return output
