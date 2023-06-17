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
import contextvars
from tenacity import retry,stop_after_attempt,wait_random
from rich.progress import Progress
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn
)
from rich.panel import Panel
from rich.console import Group
from rich.live import Live
from rich.style import Style
import arrow
import arrow
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
import ofscraper.utils.paths as paths
from ..utils import auth
import ofscraper.utils.console as console
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.args as args_


from diskcache import Cache
cache = Cache(paths.getcachepath())
log=logging.getLogger(__package__)
attempt = contextvars.ContextVar("attempt")

sem = semaphoreDelayed(constants.MAX_SEMAPHORE)



async def get_messages(headers, model_id):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue"),),TextColumn("Getting Messages...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    global tasks
    


    tasks=[]
    responseArray=[]
    page_count=0
    #require a min num of posts to be returned
    min_posts=50
    with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.shared_console): 
        oldmessages=cache.get(f"messages_{model_id}",default=[]) if not args_.getargs().no_cache else []
        oldmsgset=set(map(lambda x:x.get("id"),oldmessages))
        log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")
        oldmessages=list(filter(lambda x:(x.get("createdAt") or x.get("postedAt"))!=None,oldmessages))
        startdex=0 if len(oldmessages)==0 else \
        max(([i for i in range(len(oldmessages)) if arrow.get(oldmessages[i].get("createdAt") or oldmessages[i].get("postedAt")) <=(args_.getargs().before or arrow.now())] or [len(oldmessages)])[0]-1,0)
        log.debug(f"Setting Start Index at {startdex}")
        postedAtArray=list(map(lambda x:x["id"],sorted(oldmessages,key=lambda x:arrow.get(x.get("createdAt") or x.get("postedAt") ).float_timestamp,reverse=True)))
        postedAtArray=postedAtArray[startdex:]

    
        
     
        if len(postedAtArray)>min_posts:
            splitArrays=[postedAtArray[i:i+min_posts] for i in range(0, len(postedAtArray), min_posts)]
            #use the previous split for message_id
            tasks.append(asyncio.create_task(scrape_messages(headers,model_id,job_progress,message_id=None if startdex==0 else splitArrays[0][0] ,required_ids=set(splitArrays[0]))))
            [tasks.append(asyncio.create_task(scrape_messages(headers,model_id,job_progress,required_ids=set(splitArrays[i]),message_id=splitArrays[i-1][-1])))
            for i in range(1,len(splitArrays)-1)]
            # keeping grabbing until nothing left
            tasks.append(asyncio.create_task(scrape_messages(headers,model_id,job_progress,message_id=splitArrays[-2][-1])))
        else:
            tasks.append(asyncio.create_task(scrape_messages(headers,model_id,job_progress,message_id=None if startdex==0 else postedAtArray[0])))
    
    
        
        

        page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True)


        while len(tasks)!=0:
            for coro in asyncio.as_completed(tasks):
                result=await coro or []
                page_count=page_count+1
                overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                responseArray.extend(result)
            tasks=list(filter(lambda x:x.done()==False,tasks))
        overall_progress.remove_task(page_task)  
    unduped=[]
    dupeSet=set()
    log.debug(f"[bold]Messages Count with Dupes[/bold] {len(responseArray)} found")
    for message in responseArray:
        if message["id"] in dupeSet:
            continue
        dupeSet.add(message["id"])
        oldmsgset.discard(message["id"])       
        unduped.append(message)
    if len(oldmsgset)==0 and not (args_.getargs().before or args_.getargs().after):
        cache.set(f"messages_{model_id}",unduped,expire=constants.RESPONSE_EXPIRY)
        cache.set(f"message_check_{model_id}",oldmessages,expire=constants.CHECK_EXPIRY)

        cache.close()
    elif len(oldmsgset)>0 and not (args_.getargs().before or args_.getargs().after):
        cache.set(f"messages_{model_id}",[],expire=constants.RESPONSE_EXPIRY)
        cache.set(f"message_check_{model_id}",[],expire=constants.CHECK_EXPIRY)
        cache.close()
        log.debug("Some messages where not retrived resetting cache")

    return unduped    

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_messages(headers, model_id, progress,message_id=None,required_ids=None) -> list:
    global sem
    global tasks
    messages=None
    attempt.set(attempt.get(0) + 1)
    ep = constants.messagesNextEP if message_id else constants.messagesEP
    url = ep.format(model_id, message_id)
    log.debug(f"{message_id if message_id else 'init'}{url}")


    async with sem:
        task=progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}: Message ID-> {message_id if message_id else 'initial'}")
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))
            r = await c.get(url, timeout=None)
    if not r.is_error:
        messages = r.json()['list']
        if not messages:
            messages=[]
        if len(messages)==0:
            log.debug(f"{message_id if message_id else 'init id'} -> number of messages found 0")
        elif len(messages)>0:
            log.debug(f"{message_id if message_id else 'init id'} -> number of messages found {len(messages)}")
            log.debug(f"{message_id if message_id else 'init id'} -> first date {messages[-1].get('createdAt') or messages[0].get('postedAt')}")
            log.debug(f"{message_id if message_id else 'init id'} -> first ID {messages[0]['id']}")
            log.debug(f"{message_id if message_id else 'init id'} -> last date {messages[-1].get('createdAt') or messages[0].get('postedAt')}")
            log.debug(f"{message_id if message_id else 'init id'} -> last ID {messages[-1]['id']}")    
            if (arrow.get( messages[-1].get("createdAt") or messages[-1].get("postedAt")).float_timestamp<(args_.getargs().after or arrow.get(0)).float_timestamp):
                attempt.set(0)
            elif required_ids==None:
                attempt.set(0)
                tasks.append(asyncio.create_task(scrape_messages(headers, model_id,progress,message_id=messages[-1]['id'])))
            else:
                [required_ids.discard(ele["id"]) for ele in messages]
                #try once more to grab, else quit
                if len(required_ids)==1:
                    attempt.set(0)
                    tasks.append(asyncio.create_task(scrape_messages(headers, model_id,progress,message_id=messages[-1]['id'],required_ids=set())))

                elif len(required_ids)>0:
                    attempt.set(0)
                    tasks.append(asyncio.create_task(scrape_messages(headers, model_id,progress,message_id=messages[-1]['id'],required_ids=required_ids)))
    else:
        log.debug(f"[bold]message request status code:[/bold]{r.status_code}")
        log.debug(f"[bold]message response:[/bold] {r.content.decode()}")
        log.debug(f"[bold]message headers:[/bold] {r.headers}")

        progress.remove_task(task)
        r.raise_for_status()

    progress.remove_task(task)
    return messages



