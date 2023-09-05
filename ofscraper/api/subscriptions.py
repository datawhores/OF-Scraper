r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn
)
from rich.style import Style

import arrow
console=Console()
from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type
from ..constants import subscriptionsEP,NUM_TRIES,subscriptionsActiveEP,subscriptionsExpiredEP
import ofscraper.constants as constants
log=logging.getLogger("shared")
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args as args_
from ofscraper.utils.run_async import run

@run
async def get_subscriptions(subscribe_count,account="active"):
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        
        with Progress(  SpinnerColumn(style=Style(color="blue")),TextColumn("{task.description}")) as progress:
            task1=progress.add_task(f'Getting your {account} subscriptions (this may take awhile)...')
            async with sessionbuilder.sessionBuilder() as c: 
                if account=="active":out=await activeHelper(subscribe_count,c)
                else:out= await expiredHelper(subscribe_count,c)
                progress.remove_task(task1)
        outdict={}
        for ele in out:
            outdict[ele["id"]]=ele
        log.debug(f"Total {account} subscriptions found {len(outdict.values())}")
        return list(outdict.values())

async def activeHelper(subscribe_count,c):
    out=[]
    global tasks
    global new_tasks

    if constants.OFSCRAPER_RESERVED_LIST in args_.getargs().black_list or constants.OFSCRAPER_ACTIVE_LIST in args_.getargs().black_list:
        return[]
    if constants.OFSCRAPER_RESERVED_LIST not in args_.getargs().user_list and constants.OFSCRAPER_ACTIVE_LIST not in args_.getargs().user_list:
        return []
    funct=scrape_subscriptions_active

    tasks = [asyncio.create_task(funct(c,offset)) for offset in  range(0, subscribe_count+1, 10)] 
    new_tasks=[]
    while tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED) 
        for result in done:
            try:
                result=await result
            except Exception as E:
                log.debug(E)
                continue
            out.extend(result)
        tasks = list(pending)
        tasks.extend(new_tasks)
        new_tasks=[]
    
    return out    
   


async def expiredHelper(subscribe_count,c):
    out=[]
    global tasks
    global new_tasks

    if constants.OFSCRAPER_RESERVED_LIST in args_.getargs().black_list or constants.OFSCRAPER_EXPIRED_LIST in args_.getargs().black_list:
        return[]
    if constants.OFSCRAPER_RESERVED_LIST not in args_.getargs().user_list and constants.OFSCRAPER_EXPIRED_LIST not in args_.getargs().user_list:
        return []
    funct=scrape_subscriptions_disabled

    tasks = [asyncio.create_task(funct(c,offset)) for offset in  range(0, subscribe_count+1, 10)] 
    new_tasks=[]
    while tasks:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED) 
        for result in done:
            try:
                result=await result
            except Exception as E:
                log.debug(E)
                continue
            out.extend(result)
        tasks = list(pending)
        tasks.extend(new_tasks)
        new_tasks=[]
    
    return out    
   









@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_subscriptions_active(c,offset=0,num=0) -> list:
        async with c.requests( subscriptionsActiveEP.format(offset))() as r:
            if r.ok:
                subscriptions = (await r.json_())["list"]
                if len(subscriptions)==0:
                     return subscriptions
                log.debug(f"usernames offset {offset}: usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}")      
                if num+len(subscriptions)<10:
                    new_tasks.append(asyncio.create_task(scrape_subscriptions_active(c,offset=offset+len(subscriptions),num= num+len(subscriptions))))
                    
                return subscriptions
            else:
                log.debug(f"[bold]subscriptions response status code:[/bold]{r.status}")
                log.debug(f"[bold]subscriptions response:[/bold] {await r.text_()}")
                log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
                r.raise_for_status()
            

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_subscriptions_disabled(c,offset=0,num=0) -> list:
        async with c.requests( subscriptionsExpiredEP.format(offset))() as r:
            if r.ok:
                subscriptions = (await r.json_())["list"]
                if len(subscriptions)==0:
                     return subscriptions
                log.debug(f"usernames offset {offset}: usernames retrived -> {list(map(lambda x:x.get('username'),subscriptions))}")      
                if num+len(subscriptions)<10:
                    new_tasks.append(asyncio.create_task(scrape_subscriptions_disabled(c,offset=offset+len(subscriptions),num= num+len(subscriptions))))
                    
                return subscriptions
            else:
                log.debug(f"[bold]subscriptions response status code:[/bold]{r.status}")
                log.debug(f"[bold]subscriptions response:[/bold] {await r.text_()}")
                log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
                r.raise_for_status()

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def sort_list(c) -> list:
        async with c.requests( constants.sortSubscriptions,method="post",json={
  "order": "users.name",
  "direction": "desc",
  "type": "all"
})() as r:
            if r.ok:
                None
            else:
                log.debug(f"[bold]subscriptions response status code:[/bold]{r.status}")
                log.debug(f"[bold]subscriptions response:[/bold] {await r.text_()}")
                log.debug(f"[bold]subscriptions headers:[/bold] {r.headers}")
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
    



