r"""
                                                             
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import time
import asyncio
import logging
import contextvars
import math
import httpx
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
import ofscraper.constants as constants
from ..utils import auth
from ..utils.paths import getcachepath
import ofscraper.utils.console as console

from diskcache import Cache
cache = Cache(getcachepath())
log=logging.getLogger(__package__)
attempt = contextvars.ContextVar("attempt")
@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_pinned_posts(headers, model_id,timestamp=0) -> list:
    with httpx.Client(http2=True, headers=headers) as c:
        ep = constants.timelinePinnedNextEP if timestamp else constants.timelinePinnedEP
        url = ep.format(model_id, timestamp)
        # url = timelinePinnedEP.format(model_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['list']
        r.raise_for_status()
        log.debug(f"[bold]pinned request status code:[/bold]{r.status_code}")
        log.debug(f"[bold]pinned response:[/bold] {r.content.decode()}")

def get_pinned_post(headers,model_id,username):
    return scrape_pinned_posts(headers,model_id)
   
@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
async def scrape_timeline_posts(headers, model_id,progress, timestamp=None,required_ids=None) -> list:
    global sem 
    global tasks
    attempt.set(attempt.get(0) + 1)
    if timestamp:
        log.debug(arrow.get(math.trunc(float(timestamp))))
        timestamp=str(timestamp)
        ep = constants.timelineNextEP
        url = ep.format(model_id, timestamp)
    else:
        ep=constants.timelineEP
        url=ep.format(model_id)
    log.debug(url)
    async with sem:
        task=progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}: Timestamp -> {arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}",visible=True)
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))
            r = await c.get(url , timeout=None)
            if not r.is_error:
                progress.remove_task(task)
                posts = r.json()['list']
                if not posts:
                    return []
                elif len(posts)==0:
                    return []
                elif required_ids==None:
                    attempt.set(0)
                    tasks.append(asyncio.create_task(scrape_timeline_posts(headers, model_id,progress,timestamp=posts[-1]['postedAtPrecise'])))
                else:
                    [required_ids.discard(float(ele["postedAtPrecise"])) for ele in posts]

                    #try once more to get id if only 1 left
                    if len(required_ids)==1:
                        attempt.set(0)
                        tasks.append(asyncio.create_task(scrape_timeline_posts(headers, model_id,progress,timestamp=posts[-1]['postedAtPrecise'],required_ids=set())))

                    elif len(required_ids)>0:
                        attempt.set(0)
                        tasks.append(asyncio.create_task(scrape_timeline_posts(headers, model_id,progress,timestamp=posts[-1]['postedAtPrecise'],required_ids=required_ids)))
                return posts
            log.debug(f"[bold]timeline request status code:[/bold]{r.status_code}")
            log.debug(f"[bold]timeline response:[/bold] {r.content.decode()}")
            r.raise_for_status()

async def get_timeline_post(headers,model_id):
    global sem
    sem = asyncio.Semaphore(8)
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting timeline media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))
    with Live(progress_group, refresh_per_second=5,console=console.shared_console): 

        oldtimeline=cache.get(f"timeline_{model_id}",default=[])
        oldtimeset=set(map(lambda x:x.get("id"),oldtimeline))
        log.debug(f"[bold]Timeline Cache[/bold] {len(oldtimeline)} found")
        oldtimeline=list(filter(lambda x:x.get("postedAtPrecise")!=None,oldtimeline))
        postedAtArray=sorted(list(map(lambda x:float(x["postedAtPrecise"]),oldtimeline)))
        global tasks
        tasks=[]
        min_posts=50
        if len(postedAtArray)>min_posts:
            splitArrays=[postedAtArray[i:i+min_posts] for i in range(0, len(postedAtArray), min_posts)]
            #use the previous split for timesamp
            tasks.append(asyncio.create_task(scrape_timeline_posts(headers,model_id,job_progress,required_ids=set(splitArrays[0]))))
            [tasks.append(asyncio.create_task(scrape_timeline_posts(headers,model_id,job_progress,required_ids=set(splitArrays[i]),timestamp=splitArrays[i-1][-1])))
            for i in range(1,len(splitArrays)-1)]
            # keeping grabbing until nothign left
            tasks.append(asyncio.create_task(scrape_timeline_posts(headers,model_id,job_progress,timestamp=splitArrays[-2][-1])))
        else:
            tasks.append(asyncio.create_task(scrape_timeline_posts(headers,model_id,job_progress)))
    
    
       
        responseArray=[]
    
    
        page_count=0 
        page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True)
        while len(tasks)!=0:
            for coro in asyncio.as_completed(tasks):
                result=await coro or []
                page_count=page_count+1
                overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                responseArray.extend(result)
            time.sleep(2)
            tasks=list(filter(lambda x:x.done()==False,tasks))
        overall_progress.remove_task(page_task)
    unduped=[]
    dupeSet=set()
    log.debug(f"[bold]Timeline Count with Dupes[/bold] {len(responseArray)} found")
    for post in sorted(responseArray,key=lambda x:x["postedAtPrecise"]):
        if post["id"] in dupeSet:
            continue
        dupeSet.add(post["id"])
        oldtimeset.discard(post["id"])
        unduped.append(post)
    log.debug(f"[bold]Timeline Count without Dupes[/bold] {len(unduped)} found")
    if len(oldtimeset)==0:
        cache.set(f"timeline_{model_id}",unduped,expire=constants.RESPONSE_EXPIRY)
        cache.close()
    else:
        cache.set(f"timeline_{model_id}",[],expire=constants.RESPONSE_EXPIRY)
        cache.close()
        log.debug("Some post where not retrived resetting cache")

    return unduped                                

def get_archive_post(headers,model_id):
    return scrape_archived_posts(headers,model_id)
   

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_archived_posts(headers, model_id, timestamp=0) -> list:
    ep = constants.archivedNextEP if timestamp else constants.archivedEP
    url = ep.format(model_id, timestamp)
    with httpx.Client(http2=True, headers=headers) as c:
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            posts = r.json()['list']
            if not posts:
                return posts
            posts += scrape_archived_posts(
                headers, model_id, posts[-1]['postedAtPrecise'])
            return posts
        r.raise_for_status()
        log.debug(f"[bold]archived request status code:[/bold]{r.status_code}")
        log.debug(f"[bold]archived response:[/bold] {r.content.decode()}")

def get_individual_post(id,client=None):
    headers = auth.make_headers(auth.read_auth())
    with client or httpx.Client(http2=True, headers=headers) as c:
        url=f"https://onlyfans.com/api2/v2/posts/{id}?skip_users=all"
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))
        r=c.get(url)
        if not r.is_error:
            return r.json()
        log.debug(f"{r.status_code}")
        log.debug(f"{r.content.decode()}")

# https://onlyfans.com/519930312/mbrownrae
# https://onlyfans.com/api2/v2/posts/519930312?skip_users=all
# https://onlyfans.com/api2/v2/posts/531178660?skip_users=all