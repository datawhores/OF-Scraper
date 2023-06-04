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
import ofscraper.constants as c
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.console as console

log=logging.getLogger(__package__)
sem = semaphoreDelayed(1)
attempt = contextvars.ContextVar("attempt")

async def get_highlight_post(headers,model_id):
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
        tasks.append(asyncio.create_task(scrape_highlights(headers,model_id,job_progress)))
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
async def scrape_highlights(headers, user_id,job_progress) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    highlights_=None; stories=None
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)

    async with httpx.AsyncClient(http2=True, headers=headers) as c:
        url_stories = constants.highlightsWithStoriesEP.format(user_id)
        url_story = constants.highlightsWithAStoryEP.format(user_id)
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url_stories, headers))
        r_multiple = await c.get(url_stories, timeout=None)
        c.headers.update(auth.create_sign(url_story, headers))
        r_one = await c.get(url_story, timeout=None)
      
        # highlights_, stories
        sem.release()
    if not r_multiple.is_error and not r_one.is_error:
        attempt.set(0)
        log.debug(f"[bold]Highlight Post Count without Dupes[/bold] {len(r_multiple.json())} found")
        log.debug(f"[bold]Story Post Count without Dupes[/bold] {len(r_one.json())} found")
        highlights_, stories =get_highlightList(r_multiple.json()),r_one.json()
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


    









