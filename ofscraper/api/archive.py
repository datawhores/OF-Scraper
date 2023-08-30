r"""
                                                             
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import logging
import contextvars
import math
from diskcache import Cache
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
import ofscraper.constants as constants
from ..utils.paths import getcachepath
import ofscraper.utils.console as console
import ofscraper.utils.args as args_
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.db.operations as operations
import ofscraper.utils.config as config_



log=logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")



sem = semaphoreDelayed(constants.AlT_SEM)
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_archived_posts(c, model_id,progress, timestamp=None,required_ids=None) -> list:
    global tasks
    global sem
    posts=None
    attempt.set(attempt.get(0) + 1)
    
    if timestamp and   (float(timestamp)>(args_.getargs().before or arrow.now()).float_timestamp):
        return []
    if timestamp:
        ep = constants.archivedNextEP
        url = ep.format(model_id, str(timestamp))
    else:
        ep=constants.archivedEP
        url=ep.format(model_id)
    log.debug(url)
    async with sem:
        
        task=progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}: Timestamp -> {arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}",visible=True)
        async with c.requests(url)() as r:  
            if r.ok:
                progress.remove_task(task)
                posts =(await r.json_())['list']
                log_id=f"timestamp:{arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}"
                if not posts:
                    posts= []
                if len(posts)==0:
                    log.debug(f" {log_id} -> number of post found 0")
                elif len(posts)>0:
                    log.debug(f"{log_id} -> number of archived post found {len(posts)}")
                    log.debug(f"{log_id} -> first date {posts[0].get('createdAt') or posts[0].get('postedAt')}")
                    log.debug(f"{log_id} -> last date {posts[-1].get('createdAt') or posts[-1].get('postedAt')}")
                    log.debug(f"{log_id} -> found archived post IDs {list(map(lambda x:x.get('id'),posts))}")
                    log.trace("{log_id} -> archive raw {posts}".format(log_id=log_id,posts=  "\n\n".join(list(map(lambda x:f"scrapeinfo archive: {str(x)}",posts)))))

                    if required_ids==None:
                        attempt.set(0)
                        new_tasks.append(asyncio.create_task(scrape_archived_posts(c, model_id,progress,timestamp=posts[-1]['postedAtPrecise'])))
                    else:
                        [required_ids.discard(float(ele["postedAtPrecise"])) for ele in posts]

    
                        if len(required_ids)>0 and float(timestamp or 0)<max(required_ids):
                            attempt.set(0)
                            new_tasks.append(asyncio.create_task(scrape_archived_posts(c, model_id,progress,timestamp=posts[-1]['postedAtPrecise'],required_ids=required_ids)))
            else:
                    log.debug(f"[bold]archived response status code:[/bold]{r.status}")
                    log.debug(f"[bold]archived response:[/bold] {await r.text_()}")
                    log.debug(f"[bold]archived headers:[/bold] {r.headers}")
                    progress.remove_task(task)
                    r.raise_for_status()
    return posts

async def get_archived_media(model_id,username,after=None): 
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting archived media...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))
        global tasks
        global new_tasks
        tasks=[]
        new_tasks=[]
        min_posts=50
        responseArray=[]
        page_count=0
        setCache=True if not args_.getargs().after else False

        with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()): 
            
            async with sessionbuilder.sessionBuilder()  as c: 


                if not args_.getargs().no_cache:  oldarchived=cache.get(f"archived__{model_id}",default=[])
                else:  oldarchived=[];setCache=False



                log.trace("oldarchive {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"oldarchive: {str(x)}",oldarchived)))))
                log.debug(f"[bold]Archived Cache[/bold] {len(oldarchived)} found")
                oldarchived=list(filter(lambda x:x.get("postedAtPrecise")!=None,oldarchived))
                postedAtArray=sorted(list(map(lambda x:float(x["postedAtPrecise"]),oldarchived)))
                after=after or get_after(model_id,username)
                log.debug(f"setting after for archive to {after} for {username}")
                filteredArray=list(filter(lambda x:x>=after,postedAtArray)) if len(postedAtArray)>0 else []
                

                if len(filteredArray)>min_posts:
                    splitArrays=[filteredArray[i:i+min_posts] for i in range(0, len(filteredArray), min_posts)]
                    #use the previous split for timesamp
                    tasks.append(asyncio.create_task(scrape_archived_posts(c,model_id,job_progress,required_ids=set(splitArrays[0]),timestamp= args_.getargs().after.float_timestamp if args_.getargs().after else None)))
                    [tasks.append(asyncio.create_task(scrape_archived_posts(c,model_id,job_progress,required_ids=set(splitArrays[i]),timestamp=splitArrays[i-1][-1])))
                    for i in range(1,len(splitArrays)-1)]
                    # keeping grabbing until nothign left
                    tasks.append(asyncio.create_task(scrape_archived_posts(c,model_id,job_progress,timestamp=splitArrays[-2][-1])))
                else:
                    tasks.append(asyncio.create_task(scrape_archived_posts(c,model_id,job_progress,timestamp=after)))
            

                page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True)
                while tasks:
                        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED) 
                        for result in done:
                            try:
                                result=await result
                            except Exception as E:
                                log.debug(E)
                                continue
                            page_count=page_count+1
                            overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                            responseArray.extend(result)
                        tasks = list(pending)
                        tasks.extend(new_tasks)
                        new_tasks=[]
                overall_progress.remove_task(page_task)
        unduped={}
        log.debug(f"[bold]Archived Count with Dupes[/bold] {len(responseArray)} found")
        for post in responseArray:
            id=post["id"]
            if unduped.get(id):continue
            unduped[id]=post
        log.trace(f"archive dupeset postids {list(unduped.keys())}")
        log.trace("archived raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo archive: {str(x)}",unduped)))))
        log.debug(f"[bold]Archived Count without Dupes[/bold] {len(unduped)} found")
        if setCache and not args_.getargs().after:
            newcache={}
            for post in oldarchived+list(map(lambda x:{"id":x.get("id"),"postedAtPrecise":x.get("postedAtPrecise")},unduped.values())):
                id=post["id"]
                if newcache.get(id):continue
                newcache[id]={"id":post.get("id"),"postedAtPrecise":post.get("postedAtPrecise")}
            cache.set(f"archived_{model_id}",list(newcache.values()),expire=constants.RESPONSE_EXPIRY)
            cache.set(f"archived_check_{model_id}",list(newcache.values()),expire=constants.CHECK_EXPIRY)
            cache.close()
        if setCache:
            lastpost=cache.get(f"archived_{model_id}_lastpost")
            post=sorted(newcache.values(),key=lambda x:x.get("postedAtPrecise"))
            if len(post)>0:
                post=post[-1]
                if not lastpost:
                    cache.set(f"archived_{model_id}_lastpost",(float(post['postedAtPrecise']),post["id"]))
                    cache.close()
                if lastpost and float(post['postedAtPrecise'])>lastpost[0]:
                    cache.set(f"archived_{model_id}_lastpost",(float(post['postedAtPrecise']),post["id"]))
                    cache.close()    
        if setCache and after==0:
            firstpost=cache.get(f"archived_{model_id}_firstpost")
            post=sorted(newcache.values(),key=lambda x:x.get("postedAtPrecise"))
            if len(post)>0:  
                post=post[0]
                if not firstpost:
                    cache.set(f"archived_{model_id}_firstpost",(float(post['postedAtPrecise']),post["id"]))
                    cache.close()
                if firstpost and float(post['postedAtPrecise'])<firstpost[0]:
                    cache.set(f"archived_{model_id}_firstpost",(float(post['postedAtPrecise']),post["id"]))
                    cache.close()

    return list(unduped.values()  )                             

def get_after(model_id,username):
    return 0
    # cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    # if args_.getargs().after:
    #     return args_.getargs().after.float_timestamp
    # if not cache.get(f"archived_{model_id}_last post") or not cache.get(f"archived_{model_id}_firstpost"):
    #     log.debug("initial archived to 0")
    #     return 0
    # if len(list(filter(lambda x:x[-2]==0,operations.get_archived_media(model_id=model_id,username=username))))==0:
    #     log.debug("set initial archived to last post")
    #     return cache.get(f"archived_{model_id}_lastpost")[0]
    # else:
    #     log.debug("archived archived to 0")
    #     return 0
