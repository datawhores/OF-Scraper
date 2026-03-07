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
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        # Pass the generator function as a list to the orchestrator
        return await process_task([scrape_subscriptions_active(c)])


async def get_all_expired_subscriptions(subscribe_count):
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        return await process_task([scrape_subscriptions_disabled(c)])


async def activeHelper(subscribe_count, c):
    # Blacklist/Reserved list logic check
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

    return await process_task([scrape_subscriptions_active(c)])


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

    return await process_task([scrape_subscriptions_disabled(c)])


async def process_task(generators):
    """
    Fixed Orchestrator: Consumes async generators and returns a final LIST.
    This satisfies the 'await' in retriver.py.
    """
    output = []
    seen = set()

    # Iterate through the provided generator workers
    for gen in generators:
        try:
            # Consuming the AsyncGenerator using 'async for'
            async for batch in gen:
                if batch:
                    users = [
                        user
                        for user in batch
                        if user["id"] not in seen and not seen.add(user["id"])
                    ]
                    output.extend(users)
        except Exception as E:
            log.debug("Failed in subscription processing loop")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            continue
    return output


async def scrape_subscriptions_active(c, offset=0):
    """
    Async Generator Worker Loop for active subscriptions.
    Yields batches page-by-page.
    """
    current_offset = offset
    while True:
        url = of_env.getattr("subscriptionsActiveEP").format(current_offset)
        try:
            log.debug(f"usernames active offset {current_offset}")
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Subscription API Error: {r.status}")
                    break

                response = await r.json_()
                subscriptions = response.get("list", [])

                if subscriptions:
                    yield subscriptions

                if response.get("hasMore") is not True or not subscriptions:
                    break

                current_offset += len(subscriptions)

        except asyncio.TimeoutError:
            log.debug(f"Task timed out {url}")
            break
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break


async def scrape_subscriptions_disabled(c, offset=0):
    """
    Async Generator Worker Loop for expired subscriptions.
    Yields batches page-by-page.
    """
    current_offset = offset
    while True:
        url = of_env.getattr("subscriptionsExpiredEP").format(current_offset)
        try:
            log.debug(f"usernames offset expired {current_offset}")
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Subscription API Error: {r.status}")
                    break

                response = await r.json_()
                subscriptions = response.get("list", [])

                if subscriptions:
                    yield subscriptions

                if response.get("hasMore") is not True or not subscriptions:
                    break

                current_offset += len(subscriptions)

        except asyncio.TimeoutError:
            log.debug(f"Task timed out {url}")
            break
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
