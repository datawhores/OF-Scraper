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

import contextvars
import logging
import traceback

from rich.console import Console
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
console = Console()
sem = None


def get_user_list_helper():
    out = read_args.retriveArgs().user_list or data.get_default_userlist()
    if isinstance(out, str):
        out = out.split(",")
    return set(map(lambda x: x.lower().strip(), out))


def get_black_list_helper():
    out = read_args.retriveArgs().black_list or data.get_default_blacklist()
    if isinstance(out, str):
        out = out.split(",")
    return set(map(lambda x: x.lower().strip(), out))


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
