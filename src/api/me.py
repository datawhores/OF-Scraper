r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import httpx
from rich.console import Console
console=Console()
from tenacity import retry,stop_after_attempt,wait_random
from ..constants import meEP,subscribeCountEP
from ..utils import auth, encoding

@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_user(headers):
    with httpx.Client(http2=True, headers=headers) as c:
        url = meEP

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()
        r.raise_for_status()


def parse_user(profile):
    name = encoding.encode_utf_16(profile['name'])
    username = profile['username']
    return (name, username)


def print_user(name, username):
    console.print(f'Welcome, {name} | {username}')
@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
def parse_subscriber_count(headers):
    with httpx.Client(http2=True, headers=headers) as c:
        url = subscribeCountEP
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))
        r = c.get(url, timeout=None)
        if not r.is_error:
            data=r.json()
            return data["subscriptions"]["all"]
        r.raise_for_status()

