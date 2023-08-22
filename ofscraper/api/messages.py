r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import logging
import contextvars
from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type
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
from diskcache import Cache
from ..utils.paths import getcachepath
import ofscraper.db.operations as operations
import ofscraper.constants as constants
import ofscraper.utils.paths as paths
import ofscraper.utils.console as console
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.args as args_
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.config as config_

log=logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")

sem = semaphoreDelayed(constants.MAX_SEMAPHORE)



async def get_messages(model_id,username,after=None):
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue"),),TextColumn("Getting Messages...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))
    setCache=True if not args_.getargs().after else False

    global tasks
    


    tasks=[]
    responseArray=[]
    page_count=0
    #require a min num of posts to be returned
    min_posts=50
    with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.get_shared_console()): 
        async with sessionbuilder.sessionBuilder() as c: 
            if not args_.getargs().no_cache:oldmessages=cache.get(f"messages_{model_id}",default=[])  
            else: oldmessages=[];setCache=False
            log.trace("oldmessage {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"oldmessages: {str(x)}",oldmessages)))))
            oldmessages=list(filter(lambda x:(x.get("date"))!=None,oldmessages))
            log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")

            sorted(oldmessages,key=lambda x:x.get("date"),reverse=True)
            after=after or get_after(model_id,username)
            filteredArray=list(filter(lambda x:x.get("date")>=after, oldmessages))
            IDArray=list(map(lambda x:x.get("id"),filteredArray))
            postedAtArray=list(map(lambda x:x.get("date"),filteredArray))
            
            if len(IDArray)>min_posts:
                splitArraysID=[IDArray[i:i+min_posts] for i in range(0, len(IDArray), min_posts)]
                splitArraysTime=[postedAtArray[i:i+min_posts] for i in range(0, len(postedAtArray), min_posts)]

                #use the previous split for message_id

                tasks.append(asyncio.create_task(scrape_messages(c,model_id,job_progress,message_id=None if len(filteredArray)==len(oldmessages) else splitArraysID[0][0] ,required_ids=set(splitArraysTime[0]))))
                [tasks.append(asyncio.create_task(scrape_messages(c,model_id,job_progress,required_ids=set(splitArraysTime[i]),message_id=splitArraysID[i-1][-1])))
                for i in range(1,len(splitArraysID)-1)]
                # keeping grabbing until nothing left
                tasks.append(asyncio.create_task(scrape_messages(c,model_id,job_progress,message_id=splitArraysID[-2][-1])))
            else:
                tasks.append(asyncio.create_task(scrape_messages(c,model_id,job_progress,message_id=None if len(filteredArray)==len(oldmessages) else postedAtArray[0])))
        
    
            page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True)


            while len(tasks)!=0:
                for coro in asyncio.as_completed(tasks):
                    try:
                        result=await coro or []
                    except:
                        setCache=False
                        continue
                    page_count=page_count+1
                    overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                    responseArray.extend(result)
                tasks=list(filter(lambda x:x.done()==False,tasks))
            overall_progress.remove_task(page_task)  
    unduped={}
    dupeSet=set()
    log.debug(f"[bold]Messages Count with Dupes[/bold] {len(responseArray)} found")


    for message in responseArray:
        id=message["id"]
        if unduped.get(id):continue
        unduped[id]=message

    log.trace(f"messages dupeset messageids {dupeSet}")
    log.trace("messages raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo message: {str(x)}",unduped)))))

    if setCache:
        newcache={}
        for message in oldmessages+list(unduped.values()):
            id=message["id"]
            if newcache.get(id):continue
            newcache[id]={"id":message.get("id"), \
                     "date":arrow.get(message.get("createdAt") or message.get("postedAt")).float_timestamp,\
                     "createdAt":message.get("createdAt") or message.get("postedAt") }
        cache.set(f"messages_{model_id}",list(newcache.values()),expire=constants.RESPONSE_EXPIRY)
        cache.set(f"message_check__{model_id}",list(newcache.values()),expire=constants.CHECK_EXPIRY)
        cache.close()

    if setCache:
        lastpost=cache.get(f"messages_{model_id}_lastpost")
        post=sorted(newcache.values(),key=lambda x:x.get("date"))
        if len(post)>0:
            post=post[-1]
            if not lastpost:
                cache.set(f"messages_{model_id}_lastpost",(float(post['date']),post["id"]))
                cache.close()
            if lastpost and float(post['date'])>lastpost[0]:
                cache.set(f"messages_{model_id}_lastpost",(float(post['date']),post["id"]))
                cache.close()
    
    if setCache:
        lastpost=cache.get(f"messages_{model_id}_lastpost")
        post=sorted(newcache.values(),key=lambda x:x.get("date"))
        if len(post)>0:
            post=post[-1]
            if not lastpost:
                cache.set(f"messages_{model_id}_lastpost",(float(post['date']),post["id"]))
                cache.close()
            if lastpost and float(post['date'])>lastpost[0]:
                cache.set(f"messages_{model_id}_lastpost",(float(post['date']),post["id"]))
                cache.close()
            
    if setCache and after==0:
        firstpost=cache.get(f"messages_{model_id}_firstpost")
        post=sorted(newcache.values(),key=lambda x:x.get("date"))
        if len(post)>0:  
            post=post[0]
            if not firstpost:
                cache.set(f"messages_{model_id}_firstpost",(float(post['date']),post["id"]))
                cache.close()
            if firstpost and float(post['date'])<firstpost[0]:
                cache.set(f"messages_{model_id}_firstpost",(float(post['date']),post["id"]))
                cache.close()

    
    
    
    return unduped.values()    
           

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_messages(c, model_id, progress,message_id=None,required_ids=None) -> list:
    global sem
    global tasks
    messages=None
    attempt.set(attempt.get(0) + 1)
    ep = constants.messagesNextEP if message_id else constants.messagesEP
    url = ep.format(model_id, message_id)
    log.debug(f"{message_id if message_id else 'init'}{url}")
    try:
        await sem.acquire()
        async with c.requests(url=url)() as r:
            task=progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}: Message ID-> {message_id if message_id else 'initial'}")
            if r.ok:
                messages = (await r.json_())['list']
                log_id=f"offset messageid:{message_id if message_id else 'init id'}"
                if not messages:
                    messages=[]
                if len(messages)==0:
                    log.debug(f"{log_id} -> number of messages found 0")
                elif len(messages)>0:
                    log.debug(f"{log_id} -> number of messages found {len(messages)}")
                    log.debug(f"{log_id} -> first date {messages[-1].get('createdAt') or messages[0].get('postedAt')}")
                    log.debug(f"{log_id} -> last date {messages[-1].get('createdAt') or messages[0].get('postedAt')}")
                    log.debug(f"{log_id} -> found message ids {list(map(lambda x:x.get('id'),messages))}")
                    log.trace("{log_id} -> messages raw {posts}".format(log_id=log_id,posts=  "\n\n".join(list(map(lambda x:f" messages scrapeinfo: {str(x)}",messages)))))
                    timestamp=arrow.get( messages[-1].get("createdAt") or messages[-1].get("postedAt")).float_timestamp

                    if (timestamp<(args_.getargs().after or arrow.get(0)).float_timestamp):
                        attempt.set(0)
                    elif required_ids==None:
                        attempt.set(0)
                        tasks.append(asyncio.create_task(scrape_messages(c, model_id,progress,message_id=messages[-1]['id'])))
                    else:
                        [required_ids.discard(ele.get("createdAt") or ele.get("postedAt")) for ele in messages]
    
                        if len(required_ids)>0 and timestamp<max(list(required_ids)):
                            attempt.set(0)
                            tasks.append(asyncio.create_task(scrape_messages(c, model_id,progress,message_id=messages[-1]['id'],required_ids=required_ids)))
                progress.remove_task(task)

            else:
                log.debug(f"[bold]message response status code:[/bold]{r.status}")
                log.debug(f"[bold]message response:[/bold] {await r.text_()}")
                log.debug(f"[bold]message headers:[/bold] {r.headers}")

                progress.remove_task(task)
                r.raise_for_status()
    except Exception as E:
        raise E
    finally:
        sem.release()
    return messages

def get_individual_post(model_id,postid,c=None):
    with c.requests(url=constants.messageSPECIFIC.format(model_id,postid))() as r:
        if r.ok:
            log.trace(f"message raw individual {r.json()}")
            return r.json()['list'][0]
        else:
            log.debug(f"[bold]invidual message response status code:[/bold]{r.status}")
            log.debug(f"[bold]invidual message  response:[/bold] {r.text_()}")
            log.debug(f"[bold]invidual message  headers:[/bold] {r.headers}")

def get_after(model_id,username):
    cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    if args_.getargs().after:
        return args_.getargs().after.float_timestamp
    if not cache.get(f"messages_{model_id}_lastpost") or not cache.get(f"messages_{model_id}_firstpost"):
        log.debug("initial messages to 0")
        return 0
    if len(list(filter(lambda x:x[-2]==0,operations.get_messages_media(model_id=model_id,username=username))))==0:
        log.debug("set initial message to last messageid")
        return cache.get(f"messages_{model_id}_lastpost")[0]
    else:
        log.debug("initial messages to 0")
        return 0