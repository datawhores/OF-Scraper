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
import httpx
from rich.console import Console
from tenacity import retry,stop_after_attempt,wait_random
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
import ofscraper.utils.encoding as encoding
import ofscraper.utils.stdout as stdout
import ofscraper.utils.logger as logger
import ofscraper.constants as constants
import ofscraper.utils.paths as paths
log=logging.getLogger(__package__)
console=Console()

from diskcache import Cache

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MAX, max=constants.OF_MAX),reraise=True,after=lambda retry_state:print(f"Trying to login attempt:{retry_state.attempt_number}/{constants.NUM_TRIES}")) 
def scrape_user(headers):
    return _scraper_user_helper(json.dumps(headers))


@lru_cache(maxsize=None)
def _scraper_user_helper(headers):
    headers = json.loads(headers)
    cache = Cache(paths.getcachepath())
    data=cache.get(f"myinfo_{headers['user-id']}",None)
    if not data:
        with httpx.Client(http2=True, headers=headers) as c:
            url = constants.meEP
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))
            r = c.get(url, timeout=None)
            if not r.is_error:
                data=r.json()
            r.raise_for_status()
    cache.set(f"myinfo_{headers['user-id']}",data,constants.HOURLY_EXPIRY)
    cache.close()
    logger.updateSenstiveDict(data["id"],"userid")
    logger.updateSenstiveDict(data["username"],"username")
    logger.updateSenstiveDict(data["name"],"name")
    return data

def parse_user(profile):
    name = encoding.encode_utf_16(profile['name'])
    username = profile['username']

    return (name, username)


def print_user(name, username):
    with stdout.lowstdout():
        console.print(f'Welcome, {name} | {username}')
@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
def parse_subscriber_count(headers):
    with httpx.Client(http2=True, headers=headers) as c:
        url = constants.subscribeCountEP
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))
        r = c.get(url, timeout=None)
        if not r.is_error:
            data=r.json()
            return data["subscriptions"]["all"]
        r.raise_for_status()

