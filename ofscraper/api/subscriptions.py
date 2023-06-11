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
import logging
import httpx
from rich.console import Console
import arrow
console=Console()
from tenacity import retry,stop_after_attempt,wait_random
from ..constants import subscriptionsEP,NUM_TRIES
from ..utils import auth, dates
import ofscraper.constants as constants
log=logging.getLogger(__package__)


async def get_subscriptions(headers, subscribe_count):
    offsets = range(0, subscribe_count, 10)
    tasks = [scrape_subscriptions(headers, offset) for offset in offsets]
    subscriptions = await asyncio.gather(*tasks)
    return list(chain.from_iterable(subscriptions))


@retry(stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
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
    datenow=arrow.now()
    data = [
        {"name":profile['username']
         ,"id":profile['id'],
         "sub-price":profile.get("currentSubscribePrice",{}),
         "regular-price":profile.get("subscribedByData").get("regularPrice") if profile.get("subscribedByData") else None,
         "promo-price": sorted(list(filter(lambda x: x.get("canClaim") == True,profile.get("promotions") or [])), key=lambda x: x["price"]),
         "expired":profile.get("subscribedByData").get("expiredAt") if profile.get("subscribedByData") else None,
         "subscribed":(profile.get("subscribedByData").get("subscribes") or [{}])[0].get("startDate") if profile.get("subscribedByData") else None ,
         "renewed":profile.get("subscribedByData").get("renewedAt") if profile.get("subscribedByData") else None,
        "active" :  arrow.get(profile.get("subscribedByData").get("expiredAt"))>datenow if profile.get("subscribedByData") else None


         } for profile in subscriptions]
    data=setpricehelper(data)
    return data

def setpricehelper(data):
    for ele in data:
        prices=list(filter(lambda x:x!=None,[ele.get("sub-price"),(ele.get("promo-price") or [{}])[0].get("price"),ele["regular-price"]]))
        if len(prices)==0:
            ele["price"]=None
        else:
            ele["price"]=min(prices)
    return data
    




