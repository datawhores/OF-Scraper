r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import logging
from rich.console import Console
from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type
import ofscraper.constants as constants
import ofscraper.utils.encoding as encoding
import ofscraper.utils.stdout as stdout
import ofscraper.utils.logger as logger
import ofscraper.constants as constants
import ofscraper.utils.paths as paths
import ofscraper.classes.sessionbuilder as sessionbuilder

log=logging.getLogger("shared")


def scrape_user():
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return _scraper_user_helper(c)


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(0),wait=wait_random(min=constants.OF_MAX, max=constants.OF_MAX),reraise=True,after=lambda retry_state:print(f"Trying to login attempt:{retry_state.attempt_number}/{constants.NUM_TRIES}")) 
def _scraper_user_helper(c):
    data=None
    with c.requests(constants.meEP)() as r:
        if r.ok:
            data=r.json_()
            logger.updateSenstiveDict(data["id"],"userid")
            logger.updateSenstiveDict(f"{data['username']} | {data['username']}|\\b{data['username']}\\b","username")
            logger.updateSenstiveDict(f"{data['name']} | {data['name']}|\\b{data['name']}\\b","name")
        else:
            log.debug(f"[bold]user request response status code:[/bold]{r.status}")
            log.debug(f"[bold]user request response:[/bold] {r.text_()}")
            log.debug(f"[bold]user request headers:[/bold] {r.headers}")
            r.raise_for_status()
                      
    return data

def parse_user(profile):
    name = encoding.encode_utf_16(profile['name'])
    username = profile['username']

    return (name, username)


def print_user(name, username):
    with stdout.lowstdout():
        Console().print(f'Welcome, {name} | {username}')
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.MAX_SEMAPHORE),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
def parse_subscriber_count():
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        with c.requests(constants.subscribeCountEP)() as r:
            if r.ok:
                data=r.json_()
                return data["subscriptions"]["active"],data["subscriptions"]["expired"]
            else:
                log.debug(f"[bold]subscriber count response status code:[/bold]{r.status}")
                log.debug(f"[bold]subscriber countresponse:[/bold] {r.text_()}")
                log.debug(f"[bold]subscriber count headers:[/bold] {r.headers}")

