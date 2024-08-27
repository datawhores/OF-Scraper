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

import ofscraper.data.api.profile as profile
import  ofscraper.runner.manager as manager2
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_utils
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@run
async def get_subscription(accounts=None):
    accounts = accounts or read_args.retriveArgs().usernames
    if not isinstance(accounts, list) and not isinstance(accounts, set):
        accounts = set([accounts])
    task1 = progress_utils.add_userlist_task(
        f"Getting the following accounts => {accounts} (this may take awhile)..."
    )
    async with manager2.Manager.aget_ofsession(
        sem_count=constants.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        out = await get_subscription_helper(c, accounts)
    progress_utils.remove_userlist_task(task1)
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
