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

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

import ofscraper.api.subscriptions.helpers as helpers
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.constants as constants
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
console = Console()


@run
async def get_subscriptions(subscribe_count, account="active"):
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        with Progress(
            SpinnerColumn(style=Style(color="blue")), TextColumn("{task.description}")
        ) as job_progress:
            task1 = job_progress.add_task(
                f"Getting your {account} subscriptions (this may take awhile)..."
            )
            async with sessionManager.sessionManager(
                sem=constants.getattr("SUBSCRIPTION_SEMS"),
                retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
                new_request_auth=True,
            ) as c:
                if account == "active":
                    out = await activeHelper(subscribe_count, c)
                else:
                    out = await expiredHelper(subscribe_count, c)
                job_progress.remove_task(task1)

        log.debug(f"Total {account} subscriptions found {len(out)}")
        return out


async def activeHelper(subscribe_count, c):
    if any(
        x in helpers.get_black_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_RESERVED_LIST"),
            constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) or any(
        x in helpers.get_black_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_ACTIVE_LIST"),
            constants.getattr("OFSCRAPER_ACTIVE_LIST_ALT"),
        ]
    ):
        return []
    if all(
        x not in helpers.get_user_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_RESERVED_LIST"),
            constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) and all(
        x not in helpers.get_user_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_ACTIVE_LIST"),
            constants.getattr("OFSCRAPER_ACTIVE_LIST_ALT"),
        ]
    ):
        return []
    funct = scrape_subscriptions_active

    tasks = [
        asyncio.create_task(funct(c, offset))
        for offset in range(0, subscribe_count + 1, 10)
    ]
    tasks.extend([asyncio.create_task(funct(c, subscribe_count + 1, recur=True))])
    return await process_task(tasks)


async def expiredHelper(subscribe_count, c):
    if any(
        x in helpers.get_black_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_RESERVED_LIST"),
            constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) or any(
        x in helpers.get_black_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_EXPIRED_LIST"),
            constants.getattr("OFSCRAPER_EXPIRED_LIST_ALT"),
        ]
    ):
        return []
    if all(
        x not in helpers.get_user_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_RESERVED_LIST"),
            constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
        ]
    ) and all(
        x not in helpers.get_user_list_helper()
        for x in [
            constants.getattr("OFSCRAPER_EXPIRED_LIST"),
            constants.getattr("OFSCRAPER_EXPIRED_LIST_ALT"),
        ]
    ):
        return []
    funct = scrape_subscriptions_disabled

    tasks = [
        asyncio.create_task(funct(c, offset))
        for offset in range(0, subscribe_count + 1, 10)
    ]
    tasks.extend([asyncio.create_task(funct(c, subscribe_count + 1, recur=True))])

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


async def scrape_subscriptions_active(c, offset=0, num=0, recur=False) -> list:
    new_tasks = []
    url = constants.getattr("subscriptionsActiveEP").format(offset)
    try:
        log.debug(f"usernames active offset {offset}")
        async with c.requests_async(url=url) as r:
            subscriptions = (await r.json_())["list"]
            log.debug(
                f"usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
            )
            if len(subscriptions) == 0:
                return subscriptions, new_tasks
            elif recur is False:
                pass
            elif (await r.json_())["hasMore"] is True:
                new_tasks.append(
                    asyncio.create_task(
                        scrape_subscriptions_active(
                            c,
                            recur=True,
                            offset=offset + len(subscriptions),
                        )
                    )
                )
            return subscriptions, new_tasks
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def scrape_subscriptions_disabled(c, offset=0, num=0, recur=False) -> list:
    new_tasks = []
    url = constants.getattr("subscriptionsExpiredEP").format(offset)
    try:
        log.debug(f"usernames offset expired {offset}")
        async with c.requests_async(url=url) as r:
            subscriptions = (await r.json_())["list"]
            log.debug(
                f"usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
            )

            if len(subscriptions) == 0:
                return subscriptions, new_tasks
            elif recur is False:
                pass
            elif (await r.json_())["hasMore"] is True:
                new_tasks.append(
                    asyncio.create_task(
                        scrape_subscriptions_disabled(
                            c,
                            recur=True,
                            offset=offset + len(subscriptions),
                        )
                    )
                )

            return subscriptions, new_tasks
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
