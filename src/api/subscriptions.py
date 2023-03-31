r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
from itertools import chain

import httpx
from rich.console import Console
console=Console()
from tenacity import retry,stop_after_attempt,wait_random
from ..constants import subscriptionsEP
from ..utils import auth, dates


async def get_subscriptions(headers, subscribe_count):
    offsets = range(0, subscribe_count, 10)
    tasks = [scrape_subscriptions(headers, offset) for offset in offsets]
    subscriptions = await asyncio.gather(*tasks)
    return list(chain.from_iterable(subscriptions))


@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
async def scrape_subscriptions(headers, offset=500) -> list:
    async with httpx.AsyncClient(http2=True, headers=headers) as c:
        url = subscriptionsEP.format(offset)
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = await c.get(subscriptionsEP.format(offset), timeout=None)
        if not r.is_error:
            subscriptions = r.json()
            return subscriptions
        r.raise_for_status()

def parse_subscriptions(subscriptions: list) -> list:
    data = [{"name":profile['username'],"id":profile['id'],"date":dates.convert_date_to_mdyhms(
        profile['subscribedByExpireDate']),"active":not profile['subscribedIsExpiredNow'],"data":profile} for profile in subscriptions]
    return data


def print_subscriptions(subscriptions: list):
    fmt = '{:>4} {:^25} {:>15} {:^35}'
    console.print(fmt.format('NUM', 'USERNAME', 'ID', 'EXPIRES ON'))
    for c, t in enumerate(subscriptions, 1):
        console.print(fmt.format(c, *t))
