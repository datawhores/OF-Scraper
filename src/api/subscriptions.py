r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

import asyncio
from itertools import chain

import httpx

from ..constants import subscriptionsEP
from ..utils import auth, dates


async def get_subscriptions(headers, subscribe_count):
    offsets = range(0, subscribe_count, 10)
    tasks = [scrape_subscriptions(headers, offset) for offset in offsets]
    subscriptions = await asyncio.gather(*tasks)
    return list(chain.from_iterable(subscriptions))


async def scrape_subscriptions(headers, offset=0) -> list:
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
    data = [(profile['username'], profile['id'], dates.convert_date_to_mdyhms(
        profile['subscribedByExpireDate'])) for profile in subscriptions]
    return data


def print_subscriptions(subscriptions: list):
    fmt = '{:>4} {:^25} {:>15} {:^35}'
    print(fmt.format('NUM', 'USERNAME', 'ID', 'EXPIRES ON'))
    for c, t in enumerate(subscriptions, 1):
        print(fmt.format(c, *t))
