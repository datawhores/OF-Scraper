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
import aiohttp
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
import ofscraper.constants as c
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.console as console

log=logging.getLogger(__package__)
sem = semaphoreDelayed(1)
attempt = contextvars.ContextVar("attempt")

async def get_highlight_post(model_id):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting highlight media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    output=[]
    page_count=0
    global tasks
    tasks=[]
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, connect=None,
                      sock_connect=None, sock_read=None)) as c: 
            tasks.append(asyncio.create_task(scrape_highlights(c,model_id,job_progress)))
            page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
            while len(tasks)!=0:
                for coro in asyncio.as_completed(tasks):
                    result=await coro or []
                    page_count=page_count+1
                    overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                    output.extend(result)
                tasks=list(filter(lambda x:x.done()==False,tasks))
            overall_progress.remove_task(page_task)  
    return output


@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_highlights( c,user_id,job_progress) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    highlights_=None; stories=None
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    headers=auth.make_headers(auth.read_auth())
  

    url_stories = constants.highlightsWithStoriesEP.format(user_id)
    url_story = constants.highlightsWithAStoryEP.format(user_id)
    r_one=await c.request("get",url_story ,verify_ssl=False,cookies=auth.add_cookies_aio(),headers=auth.create_sign(url_story , headers))
    r_multiple=await c.request("get",url_stories ,verify_ssl=False,cookies=auth.add_cookies_aio(),headers=auth.create_sign(url_stories , headers))
    
    # highlights_, stories
    sem.release()
    if  r_multiple.ok and r_one.ok:
        attempt.set(0)
        log.debug(f"[bold]Highlight Post Count without Dupes[/bold] {len(await r_multiple.json())} found")
        log.debug(f"[bold]Story Post Count without Dupes[/bold] {len(await r_one.json())} found")
        highlights_, stories =get_highlightList(await r_multiple.json()),await r_one.json()
        job_progress.remove_task(task)

    else:
        job_progress.remove_task(task)
        r_multiple.raise_for_status()
        r_one.raise_for_status()
    return  highlights_, stories 

def get_highlightList(data):
    for ele in list(filter(lambda x:isinstance(x,list),data.values())):
        if len(list(filter(lambda x:isinstance(x.get("id"),int) and data.get("hasMore")!=None,ele)))>0:
               return ele
    return []


    



def get_individual_highlight(id,client=None):
    headers = auth.make_headers(auth.read_auth())
    url=constants.highlightSPECIFIC.format(id)
    auth.add_cookies(client)
    client.headers.update(auth.create_sign(url, headers))
    r=client.get(url)
    if not r.is_error:
        return r.json()
    log.debug(f"{r.status_code}")
    log.debug(f"{r.content.decode()}")

def get_individual_stories(id,client=None):
    headers = auth.make_headers(auth.read_auth())
    url=constants.storiesSPECIFIC.format(id)
    auth.add_cookies(client)
    client.headers.update(auth.create_sign(url, headers))
    r=client.get(url)
    if not r.is_error:
        return r.json()
    log.debug(f"{r.status_code}")
    log.debug(f"{r.content.decode()}")



