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
import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.utils.context.run_async import run
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


@run
async def get_subscription(accounts=None):
    accounts = accounts or settings.get_settings().usernames
    if not isinstance(accounts, list) and not isinstance(accounts, set):
        accounts = set([accounts])
    task1 = progress_utils.userlist.add_overall_task(
        f"Getting the following accounts => {accounts} (this may take awhile)..."
    )
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        out = await get_subscription_helper(c, accounts)
    progress_utils.userlist.remove_overall_task(task1)
    outdict = {}
    for ele in filter(
        lambda x: x["username"] != of_env.getattr("DELETED_MODEL_PLACEHOLDER"),
        out,
    ):
        outdict[ele["id"]] = ele
    log.debug(f"Total subscriptions found {len(outdict.values())}")
    return list(outdict.values())


async def get_subscription_helper(c, accounts):
    output = []
    queue = asyncio.Queue()

    async def producer(account):
        try:
            # CHANGE: Use 'await' instead of 'async for'
            # because scrape_profile_helper_async returns a dict, not a generator
            result = await profile.scrape_profile_helper_async(c, account)
            if result:
                await queue.put(result)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            # Still signal that this worker is done
            await queue.put(None)

    workers = [asyncio.create_task(producer(account)) for account in accounts]
    active_workers = len(workers)

    while active_workers > 0:
        result = await queue.get()
        if result is None:
            active_workers -= 1
            continue

        log.debug(f"subscription data found for {result.get('username')} ")
        output.append(result)

    return output
