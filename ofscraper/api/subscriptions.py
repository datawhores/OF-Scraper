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
import contextvars
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
console = Console()
sem = None


@run
async def get_subscriptions(subscribe_count, account="active"):
    global sem
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))
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
        constants.getattr("OFSCRAPER_RESERVED_LIST")
        in read_args.retriveArgs().black_list
        or constants.getattr("OFSCRAPER_ACTIVE_LIST")
        in read_args.retriveArgs().black_list
    ):
        return []
    if (
        constants.getattr("OFSCRAPER_RESERVED_LIST")
        not in read_args.retriveArgs().user_list
        and constants.getattr("OFSCRAPER_ACTIVE_LIST")
        not in read_args.retriveArgs().user_list
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
        constants.getattr("OFSCRAPER_RESERVED_LIST")
        in read_args.retriveArgs().black_list
        or constants.getattr("OFSCRAPER_EXPIRED_LIST")
        in read_args.retriveArgs().black_list
    ):
        return []
    if (
        constants.getattr("OFSCRAPER_RESERVED_LIST")
        not in read_args.retriveArgs().user_list
        and constants.getattr("OFSCRAPER_EXPIRED_LIST")
        not in read_args.retriveArgs().user_list
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


async def scrape_subscriptions_active(c, offset=0, num=0, recur=False) -> list:
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))
    attempt.set(0)
    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                log.debug(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} usernames active offset {offset}"
                )
                async with c.requests(
                    constants.getattr("subscriptionsActiveEP").format(offset)
                )() as r:
                    if r.ok:
                        subscriptions = (await r.json_())["list"]
                        log.debug(
                            f"usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
                        )
                        if len(subscriptions) == 0:
                            return subscriptions
                        elif recur == False:
                            None
                        elif (await r.json_())["hasMore"] == True:
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_subscriptions_active(
                                        c,
                                        recur=True,
                                        offset=offset + len(subscriptions),
                                    )
                                )
                            )
                        return subscriptions
                    else:
                        log.debug(
                            f"[bold]subscriptions response status code:[/bold]{r.status}"
                        )
                        log.debug(
                            f"[bold]subscriptions response:[/bold] {await r.text_()}"
                        )
                        log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()


async def scrape_subscriptions_disabled(c, offset=0, num=0, recur=False) -> list:
    attempt.set(0)
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))

    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                log.debug(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} usernames offset expired {offset}"
                )
                async with c.requests(
                    constants.getattr("subscriptionsExpiredEP").format(offset)
                )() as r:
                    if r.ok:
                        subscriptions = (await r.json_())["list"]
                        log.debug(
                            f"usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}"
                        )

                        if len(subscriptions) == 0:
                            return subscriptions
                        elif recur == False:
                            None
                        elif (await r.json_())["hasMore"] == True:
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_subscriptions_disabled(
                                        c,
                                        recur=True,
                                        offset=offset + len(subscriptions),
                                    )
                                )
                            )

                        return subscriptions
                    else:
                        log.debug(
                            f"[bold]subscriptions response status code:[/bold]{r.status}"
                        )
                        log.debug(
                            f"[bold]subscriptions response:[/bold] {await r.text_()}"
                        )
                        log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()


async def sort_list(c) -> list:
    global sem
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))
    attempt.set(0)
    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                async with c.requests(
                    constants.getattr("sortSubscription"),
                    method="post",
                    json={"order": "users.name", "direction": "desc", "type": "all"},
                )() as r:
                    if r.ok:
                        None
                    else:
                        log.debug(
                            f"[bold]subscriptions response status code:[/bold]{r.status}"
                        )
                        log.debug(
                            f"[bold]subscriptions response:[/bold] {await r.text_()}"
                        )
                        log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
