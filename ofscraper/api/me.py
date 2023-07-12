r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import logging
from functools import lru_cache
import json
from rich.console import Console
from tenacity import retry,stop_after_attempt,wait_random
import ofscraper.constants as constants
import ofscraper.utils.encoding as encoding
import ofscraper.utils.stdout as stdout
import ofscraper.utils.logger as logger
import ofscraper.constants as constants
import ofscraper.utils.paths as paths
import ofscraper.classes.sessionbuilder as sessionbuilder

log=logging.getLogger(__package__)
console=Console()

from diskcache import Cache

def scrape_user(headers):
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return _scraper_user_helper(c,json.dumps(headers))


@lru_cache(maxsize=None)
@retry(stop=stop_after_attempt(0),wait=wait_random(min=constants.OF_MAX, max=constants.OF_MAX),reraise=True,after=lambda retry_state:print(f"Trying to login attempt:{retry_state.attempt_number}/{constants.NUM_TRIES}")) 
def _scraper_user_helper(c,headers):
    headers = json.loads(headers)
    cache = Cache(paths.getcachepath())
    data=cache.get(f"myinfo_{headers['user-id']}",None)
    if not data:
            with c.requests(constants.meEP)() as r:
                if r.ok:
                    data=r.json_()
                    cache.set(f"myinfo_{headers['user-id']}",data,constants.HOURLY_EXPIRY)
                    cache.close()
                    logger.updateSenstiveDict(data["id"],"userid")
                    logger.updateSenstiveDict(data["username"],"username")
                    logger.updateSenstiveDict(data["name"],"name")
                else:
                    log.debug(f"[bold]archived request status code:[/bold]{r.status}")
                    log.debug(f"[bold]archived response:[/bold] {r.text_()}")
                    log.debug(f"[bold]archived headers:[/bold] {r.headers}")
                    r.raise_for_status()
                
           
    return data

def parse_user(profile):
    name = encoding.encode_utf_16(profile['name'])
    username = profile['username']

    return (name, username)


def print_user(name, username):
    with stdout.lowstdout():
        console.print(f'Welcome, {name} | {username}')
@retry(stop=stop_after_attempt(constants.MAX_SEMAPHORE),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
def parse_subscriber_count():
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        with c.requests(constants.subscribeCountEP)() as r:
            if r.ok:
                data=r.json_()
                return data["subscriptions"]["all"]
            else:
                log.debug(f"[bold]archived request status code:[/bold]{r.status}")
                log.debug(f"[bold]archived response:[/bold] {r.text_()}")
                log.debug(f"[bold]archived headers:[/bold] {r.headers}")

