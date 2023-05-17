r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import time
import httpx
import logging
from tenacity import retry,stop_after_attempt,wait_random
from tqdm.asyncio import tqdm
import arrow
import src.constants as constants
import src.utils.auth as auth
import src.utils.paths as paths
from ..utils import auth
from diskcache import Cache
cache = Cache(paths.getcachepath())
log=logging.getLogger(__package__)




async def get_messages(headers, model_id):
    global sem
    sem = asyncio.Semaphore(8)
    oldmessages=cache.get(f"messages_{model_id}",default=[]) 
    log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")
    
    postedAtArray=list(map(lambda x:x["id"],sorted(oldmessages,key=lambda x:arrow.get(x["createdAt"]).float_timestamp,reverse=True)))
    global tasks
    tasks=[]
    
    #split and interval can't match because of breakpoints
    split=40
    interval=30
    if len(postedAtArray)>split:
        splitArrays=[postedAtArray[i:i+split] for i in range(0, len(postedAtArray), interval)]
        tasks.append(asyncio.create_task(scrape_messages(headers,model_id)))
        tasks.extend(list(map(lambda x:asyncio.create_task(scrape_messages(headers,model_id,message_id=x[0])),splitArrays[1:-1])))
        tasks.append(asyncio.create_task(scrape_messages(headers,model_id,message_id=splitArrays[-1][0],recursive=True)))
    else:
        tasks.append(asyncio.create_task(scrape_messages(headers,model_id,recursive=True)))
   
  
    
    
    responseArray=[]
    page_count=0 
    desc = 'Pages Progress: {page_count}'   

    with tqdm(desc=desc.format(page_count=page_count), colour='cyan',position=2,disable=True if logging.getLogger("src").handlers[2].level>=constants.SUPPRESS_LOG_LEVEL else False) as main_bar:
        while len(tasks)!=0:
                    for coro in asyncio.as_completed(tasks):
                        result=await coro or []
                        page_count=page_count+1
                        main_bar.set_description(desc.format(page_count=page_count), refresh=False)
                        main_bar.update()
                        responseArray.extend(result)
                    time.sleep(2)
                    tasks=list(filter(lambda x:x.done()==False,tasks))
    unduped=[]
    dupeSet=set()
    log.debug(f"[bold]Messages Count with Dupes[/bold] {len(responseArray)} found")
    for message in responseArray:
        if message["id"] in dupeSet:
            continue
        dupeSet.add(message["id"])
        unduped.append(message)       
    log.debug(f"[bold]Messages Count without Dupes[/bold] {len(unduped)} found")
    cache.set(f"messages_{model_id}",unduped,expire=constants.RESPONSE_EXPIRY) 
    cache.close()
    return unduped

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
async def scrape_messages(headers, user_id, message_id=None,recursive=False) -> list:
    ep = constants.messagesNextEP if message_id else constants.messagesEP
    url = ep.format(user_id, message_id)
    async with sem:
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))
            r = await c.get(url, timeout=None)
            if not r.is_error:
                messages = r.json()['list']
                if not messages:
                    return []
                elif len(messages)==0:
                    return messages
                elif not recursive:
                    return messages
                global tasks
                tasks.append(asyncio.create_task(scrape_messages(headers, user_id, recursive=True,message_id=messages[-1]['id'])))
                return messages
            log.debug(f"[bold]message request status code:[/bold]{r.status_code}")
            log.debug(f"[bold]message response:[/bold] {r.content.decode()}")
            r.raise_for_status()



