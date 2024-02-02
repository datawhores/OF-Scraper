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

import logging
import traceback

from tenacity import (
    Retrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.constants as constants
import ofscraper.utils.logs.helpers as log_helpers

log = logging.getLogger("shared")


def scrape_user():
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return _scraper_user_helper(c)


def _scraper_user_helper(c):
    data = None
    for _ in Retrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("LOGIN_NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
        after=lambda retry_state: print(
            f"Trying to login attempt:{retry_state.attempt_number}/{constants.getattr('NUM_TRIES')}"
        ),
    ):
        with _:
            try:
                with c.requests(constants.getattr("meEP"))() as r:
                    if r.ok:
                        data = r.json_()
                        log_helpers.updateSenstiveDict(data["id"], "userid")
                        log_helpers.updateSenstiveDict(
                            f"{data['username']} | {data['username']}|\\b{data['username']}\\b",
                            "username",
                        )
                        log_helpers.updateSenstiveDict(
                            f"{data['name']} | {data['name']}|\\b{data['name']}\\b",
                            "name",
                        )
                    else:
                        log.debug(
                            f"[bold]user request response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]user request response:[/bold] {r.text_()}")
                        log.debug(f"[bold]user request headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
            return data


def parse_subscriber_count():
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        for _ in Retrying(
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
            wait=wait_random(
                min=constants.getattr("OF_MIN"),
                max=constants.getattr("OF_MAX"),
            ),
            reraise=True,
        ):
            with _:
                try:
                    with c.requests(constants.getattr("subscribeCountEP"))() as r:
                        if r.ok:
                            data = r.json_()
                            return (
                                data["subscriptions"]["active"],
                                data["subscriptions"]["expired"],
                            )
                        else:
                            log.debug(
                                f"[bold]subscriber count response status code:[/bold]{r.status}"
                            )
                            log.debug(
                                f"[bold]subscriber countresponse:[/bold] {r.text_()}"
                            )
                            log.debug(
                                f"[bold]subscriber count headers:[/bold] {r.headers}"
                            )
                except Exception as E:
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    raise E
