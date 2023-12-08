r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import arrow
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

console = Console()
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_random

import ofscraper.constants as constants

from ..constants import (
    NUM_TRIES,
    subscriptionsActiveEP,
    subscriptionsEP,
    subscriptionsExpiredEP,
)

log = logging.getLogger("shared")
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args as args_
from ofscraper.utils.run_async import run


@run
async def get_subscriptions(subscribe_count, account="active"):
    with ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        with Progress(
            SpinnerColumn(style=Style(color="blue")), TextColumn("{task.description}")
        ) as progress:
            task1 = progress.add_task(
                f"Getting your {account} subscriptions (this may take awhile)..."
            )
            async with sessionbuilder.sessionBuilder() as c:
                if account == "active":
                    out = await activeHelper(subscribe_count, c)
                else:
                    out = await expiredHelper(subscribe_count, c)
                progress.remove_task(task1)
        outdict = {}
        for ele in out:
            outdict[ele["id"]] = ele
        log.debug(f"Total {account} subscriptions found {len(outdict.values())}")
        return list(outdict.values())


async def activeHelper(subscribe_count, c):
    out = []
    global tasks
    global new_tasks

    if (
        constants.OFSCRAPER_RESERVED_LIST in args_.getargs().black_list
        or constants.OFSCRAPER_ACTIVE_LIST in args_.getargs().black_list
    ):
        return []
    if (
        constants.OFSCRAPER_RESERVED_LIST not in args_.getargs().user_list
        and constants.OFSCRAPER_ACTIVE_LIST not in args_.getargs().user_list
    ):
        return []
    funct = scrape_subscriptions_active

    tasks = [
        asyncio.create_task(funct(c, offset))
        for offset in range(0, subscribe_count + 1, 10)
    ]
    tasks.extend([asyncio.create_task(funct(c, subscribe_count + 1, recur=True))])

    new_tasks = []
    while tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for result in done:
            try:
                result = await result
            except Exception as E:
                log.debug(E)
                continue
            out.extend(result)
        tasks = list(pending)
        tasks.extend(new_tasks)
        new_tasks = []

    return out


async def expiredHelper(subscribe_count, c):
    out = []
    global tasks
    global new_tasks

    if (
        constants.OFSCRAPER_RESERVED_LIST in args_.getargs().black_list
        or constants.OFSCRAPER_EXPIRED_LIST in args_.getargs().black_list
    ):
        return []
    if (
        constants.OFSCRAPER_RESERVED_LIST not in args_.getargs().user_list
        and constants.OFSCRAPER_EXPIRED_LIST not in args_.getargs().user_list
    ):
        return []
    funct = scrape_subscriptions_disabled

    tasks = [
        asyncio.create_task(funct(c, offset))
        for offset in range(0, subscribe_count + 1, 10)
    ]
    tasks.extend([asyncio.create_task(funct(c, subscribe_count + 1, recur=True))])

    new_tasks = []
    while tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for result in done:
            try:
                result = await result
            except Exception as E:
                log.debug(E)
                continue
            out.extend(result)
        tasks = list(pending)
        tasks.extend(new_tasks)
        new_tasks = []

    return out


@retry(
    retry=retry_if_not_exception_type(KeyboardInterrupt),
    stop=stop_after_attempt(constants.NUM_TRIES),
    wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),
    reraise=True,
)
async def scrape_subscriptions_active(c, offset=0, num=0, recur=False) -> list:
    async with c.requests(subscriptionsActiveEP.format(offset))() as r:
        if r.ok:
            subscriptions = (await r.json_())["list"]
            log.debug(
                f"usernames offset {offset}: usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
            )
            if len(subscriptions) == 0:
                return subscriptions
            elif recur == False:
                None
            elif (await r.json_())["hasMore"] == True:
                new_tasks.append(
                    asyncio.create_task(
                        scrape_subscriptions_active(
                            c, recur=True, offset=offset + len(subscriptions)
                        )
                    )
                )
            return subscriptions
        else:
            log.debug(f"[bold]subscriptions response status code:[/bold]{r.status}")
            log.debug(f"[bold]subscriptions response:[/bold] {await r.text_()}")
            log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
            r.raise_for_status()


@retry(
    retry=retry_if_not_exception_type(KeyboardInterrupt),
    stop=stop_after_attempt(constants.NUM_TRIES),
    wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),
    reraise=True,
)
async def scrape_subscriptions_disabled(c, offset=0, num=0, recur=False) -> list:
    async with c.requests(subscriptionsExpiredEP.format(offset))() as r:
        if r.ok:
            subscriptions = (await r.json_())["list"]
            log.debug(
                f"usernames offset {offset}: usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
            )
            if len(subscriptions) == 0:
                return subscriptions
            elif recur == False:
                None
            elif (await r.json_())["hasMore"] == True:
                new_tasks.append(
                    asyncio.create_task(
                        scrape_subscriptions_disabled(
                            c, recur=True, offset=offset + len(subscriptions)
                        )
                    )
                )

            return subscriptions
        else:
            log.debug(f"[bold]subscriptions response status code:[/bold]{r.status}")
            log.debug(f"[bold]subscriptions response:[/bold] {await r.text_()}")
            log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
            r.raise_for_status()


@retry(
    retry=retry_if_not_exception_type(KeyboardInterrupt),
    stop=stop_after_attempt(constants.NUM_TRIES),
    wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),
    reraise=True,
)
async def sort_list(c) -> list:
    async with c.requests(
        constants.sortSubscriptions,
        method="post",
        json={"order": "users.name", "direction": "desc", "type": "all"},
    )() as r:
        if r.ok:
            None
        else:
            log.debug(f"[bold]subscriptions response status code:[/bold]{r.status}")
            log.debug(f"[bold]subscriptions response:[/bold] {await r.text_()}")
            log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
            r.raise_for_status()


def parse_subscriptions(subscriptions: list) -> list:
    datenow = arrow.now()
    data = []
    for profile in subscriptions:
        ele = {
            "name": profile["username"],
            "id": profile["id"],
            "avatar": profile.get("avatar"),
            "header": profile.get("header"),
            "sub-price": profile.get("currentSubscribePrice", {}),
            "regular-price": profile.get("subscribedByData").get("regularPrice")
            if profile.get("subscribedByData")
            else profile.get("subscribePrice"),
            "promo-price": sorted(
                list(
                    filter(
                        lambda x: x.get("canClaim") == True,
                        profile.get("promotions") or [],
                    )
                ),
                key=lambda x: x["price"],
            ),
            "all-promo-price": sorted(
                profile.get("promotions") or [],
                key=lambda x: x["price"],
            ),
            "expired": profile.get("subscribedByData").get("expiredAt")
            if profile.get("subscribedByData")
            else None,
            "subscribed": (profile.get("subscribedByData").get("subscribes") or [{}])[
                0
            ].get("startDate")
            if profile.get("subscribedByData")
            else None,
            "renewed": profile.get("subscribedByData").get("renewedAt")
            if profile.get("subscribedByData")
            else None,
            "active": arrow.get(
                profile.get("subscribedByExpireDate")
                or (profile.get("subscribedByData", {}) or {}).get("expiredAt")
                or 0
            )
            > datenow
            or (profile.get("subscribedByData", {}) or {}).get("status")
            == "Set to Expire",
        }
        promo_price_helper(ele)
        all_promo_price_helper(ele)
        final_promo_price_helper(ele)
        final_current_price_helper(ele)
        final_renewal_price_helper(ele)
        final_regular_price_helper(ele)
        data.append(ele)
    return data


# Price Helpers


def final_promo_price_helper(ele):
    if ele.get("all-promo-price") is not None:
        ele["final-promo-price"] = ele.get("all-promo-price")
    elif ele.get("regular-price") is not None:
        ele["final-promo-price"] = ele.get("regular-price")
    else:
        ele["final-promo-price"] = 0


def final_renewal_price_helper(ele):
    if ele.get("promo-price") is not None:
        ele["final-renewal-price"] = ele.get("promo-price")
    elif ele.get("regular-price") is not None:
        ele["final-renewal-price"] = ele.get("regular-price")
    else:
        ele["final-renewal-price"] = 0


def final_current_price_helper(ele):
    if ele.get("sub-price") is not None:
        ele["final-current-price"] = ele.get("sub-price")
    elif ele.get("promo-price") is not None:
        ele["final-current-price"] = ele.get("promo-price")
    elif ele.get("regular-price") is not None:
        ele["final-current-price"] = ele.get("regular-price")
    else:
        ele["final-current-price"] = 0


def final_regular_price_helper(ele):
    if ele.get("regular-price") is not None:
        ele["final-regular-price"] = ele.get("regular-price")
    else:
        ele["final-regular-price"] = 0


def promo_price_helper(ele):
    if len(ele["promo-price"]) == 0:
        ele["promo-price"] = None
    else:
        ele["promo-price"] = ele["promo-price"][0]["price"]


def all_promo_price_helper(ele):
    if len(ele["all-promo-price"]) == 0:
        ele["all-promo-price"] = None

    else:
        ele["all-promo-price"] = ele["all-promo-price"][0]["price"]
