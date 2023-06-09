import asyncio
import contextvars
import logging
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
import ofscraper.constants as constants
from ..utils import auth
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.console as console

log=logging.getLogger(__package__)
sem = semaphoreDelayed(1)
attempt = contextvars.ContextVar("attempt")

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_pinned_posts(headers, model_id,job_progress,timestamp=0) -> list:
    global sem
    global tasks
    posts=None
    attempt.set(attempt.get(0) + 1)
    

    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    async with httpx.AsyncClient(http2=True, headers=headers) as c:
        ep = constants.timelinePinnedNextEP if timestamp else constants.timelinePinnedEP
        url = ep.format(model_id, timestamp)
        # url = timelinePinnedEP.format(model_id)
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))
        r = await c.get(url, timeout=None)
        sem.release()
    if not r.is_error:
        attempt.set(0)
        posts=r.json()['list']
        job_progress.remove_task(task)

    else:
        log.debug(f"[bold]pinned request status code:[/bold]{r.status_code}")
        log.debug(f"[bold]pinned response:[/bold] {r.content.decode()}")
        log.debug(f"[bold]pinned headers:[/bold] {r.headers}")
        job_progress.remove_task(task)
        r.raise_for_status()
    return posts


async def get_pinned_post(headers,model_id):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting pinned media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))
    
    page_count=0    
    global tasks
    tasks=[]
    output=[]
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        tasks.append(asyncio.create_task(scrape_pinned_posts(headers,model_id,job_progress)))
        page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
        while len(tasks)>0:
            for coro in asyncio.as_completed(tasks):
                result=await coro or []
                page_count=page_count+1
                overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                output.extend(result)
            tasks=list(filter(lambda x:x.done()==False,tasks))
    overall_progress.remove_task(page_task)  
    return output


   