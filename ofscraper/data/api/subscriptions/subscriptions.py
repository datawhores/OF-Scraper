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

import ofscraper.data.api.subscriptions.common as common
import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.screens as progress_utils
from ofscraper.utils.context.run_async import run
from ofscraper.utils.live.updater import userlist

log = logging.getLogger("shared")
console = Console()


@run
async def get_subscriptions(subscribe_count, account="active"):

    task1 = userlist.add_overall_task(
        f"Getting your {account} subscriptions (this may take awhile)..."
    )
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        if account == "active":
            out = await activeHelper(subscribe_count, c)
        else:
            out = await expiredHelper(subscribe_count, c)
    userlist.remove_overall_task(task1)
    log.debug(f"Total {account} subscriptions found {len(out)}")
    return out


@run
async def get_all_subscriptions(subscribe_count, account="active"):
    if account == "active":
        return await get_all_activive_subscriptions(subscribe_count)
    else:
        return await get_all_expired_subscriptions(subscribe_count)


async def get_all_activive_subscriptions(subscribe_count):
    funct = scrape_subscriptions_active
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        tasks = [
            asyncio.create_task(funct(c))
        ]
        return await process_task(tasks)


async def get_all_expired_subscriptions(subscribe_count):
    funct = scrape_subscriptions_disabled
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        tasks = [
            asyncio.create_task(funct(c))
        ]
        return await process_task(tasks)


async def activeHelper(subscribe_count, c):
    if any(
        x in common.get_black_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_RESERVED_LIST"),
            of_env.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) or any(
        x in common.get_black_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_ACTIVE_LIST"),
            of_env.getattr("OFSCRAPER_ACTIVE_LIST_ALT"),
        ]
    ):
        return []
    if all(
        x not in common.get_user_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_RESERVED_LIST"),
            of_env.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) and all(
        x not in common.get_user_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_ACTIVE_LIST"),
            of_env.getattr("OFSCRAPER_ACTIVE_LIST_ALT"),
        ]
    ):
        return []
    funct = scrape_subscriptions_active

    tasks = [
        asyncio.create_task(funct(c))
    ]
    return await process_task(tasks)


async def expiredHelper(subscribe_count, c):
    if any(
        x in common.get_black_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_RESERVED_LIST"),
            of_env.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) or any(
        x in common.get_black_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_EXPIRED_LIST"),
            of_env.getattr("OFSCRAPER_EXPIRED_LIST_ALT"),
        ]
    ):
        return []
    if all(
        x not in common.get_user_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_RESERVED_LIST"),
            of_env.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) and all(
        x not in common.get_user_list_helper()
        for x in [
            of_env.getattr("OFSCRAPER_EXPIRED_LIST"),
            of_env.getattr("OFSCRAPER_EXPIRED_LIST_ALT"),
        ]
    ):
        return []
    funct = scrape_subscriptions_disabled

    tasks = [
        asyncio.create_task(funct(c))
    ]
    return await process_task(tasks)


async def process_task(tasks):
    output = []
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                users = [
                    user
                    for user in result
                    if user["id"] not in seen and not seen.add(user["id"])
                ]
                output.extend(users)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    return output


async def scrape_subscriptions_active(c, offset=0):
    with progress_utils.setup_live("user_list"):
        new_tasks = []
        url = of_env.getattr("subscriptionsActiveEP").format(offset)
        try:
            log.debug(f"usernames active offset {offset}")
            async with c.requests_async(url=url) as r:
                response = await r.json_()
                subscriptions = response["list"]
                log.debug(
                    f"usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
                )
                if response["hasMore"] is True:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_subscriptions_active(c, offset=offset + 10)
                        )
                    )
                return subscriptions, new_tasks
        except asyncio.TimeoutError:
            raise Exception(f"Task timed out {url}")

        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            raise E


async def scrape_subscriptions_disabled(c, offset=0):
    with progress_utils.setup_live("user_list"):
        new_tasks = []
        url = of_env.getattr("subscriptionsExpiredEP").format(offset)
        try:
            log.debug(f"usernames offset expired {offset}")
            async with c.requests_async(url=url) as r:
                response = await r.json_()
                subscriptions = response["list"]
                log.debug(
                    f"usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
                )
                if response["hasMore"] is True:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_subscriptions_disabled(c, offset=offset + 10)
                        )
                    )

                return subscriptions, new_tasks
        except asyncio.TimeoutError:
            raise Exception(f"Task timed out {url}")

        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            raise E
