r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import httpx
import logging
import contextvars
from rich.progress import Progress
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn
)
from tenacity import retry,stop_after_attempt,wait_random
from rich.panel import Panel
from rich.console import Group
from rich.live import Live
from rich.style import Style
import ofscraper.constants as constants
from ..utils import auth
from ..utils.paths import getcachepath
import ofscraper.utils.console as console
import ofscraper.utils.auth as auth
import ofscraper.constants as constants
import ofscraper.api.profile as profile
from diskcache import Cache
from ..utils.paths import getcachepath
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed

cache = Cache(getcachepath())

paid_content_list_name = 'list'
log=logging.getLogger(__package__)

sem = semaphoreDelayed(1)

attempt = contextvars.ContextVar("attempt")









async def get_paid_posts(username,model_id):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting paid media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    output=[]
    global tasks
    tasks=[]
    page_count=0
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        tasks.append(asyncio.create_task(scrape_paid(username,job_progress)))
        
        page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
        while len(tasks)!=0:
            for coro in asyncio.as_completed(tasks):
                result=await coro or []
                page_count=page_count+1
                overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                output.extend(result)
            tasks=list(filter(lambda x:x.done()==False,tasks))
        overall_progress.remove_task(page_task)  
    log.debug(f"[bold]Paid Post count without Dupes[/bold] {len(output)} found")
    # set purchash check values during scan
    cache.set(f"purchased_check_{model_id}",output,expire=constants.CHECK_EXPIRY)
    return output


@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_paid(username,job_progress,offset=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list."""
    global sem
    global tasks
    media = None
    offset = 0
    headers = auth.make_headers(auth.read_auth())
    attempt.set(attempt.get(0) + 1)
    
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    async with httpx.AsyncClient(http2=True, headers=headers, follow_redirects=True) as c:
        auth.add_cookies(c)
        url = constants.purchased_contentEP.format(offset,username)
        offset += 10
        c.headers.update(auth.create_sign(url, headers))
        r = await c.get(url, timeout=None)
        sem.release()
    if not r.is_error:
        attempt.set(0)
        if "hasMore" in r.json() and r.json()['hasMore']:
            tasks.append(asyncio.create_task(scrape_paid(username,offset=offset)))
        media=list(filter(lambda x:isinstance(x,list),r.json().values()))[0]
        job_progress.remove_task(task)

    else:
        log.debug(f"[bold]paid request status code:[/bold]{r.status_code}")
        log.debug(f"[bold]paid response:[/bold] {r.content.decode()}")
        log.debug(f"[bold]paid headers:[/bold] {r.headers}")
        job_progress.remove_task(task)
        r.raise_for_status()
    return media





async def get_all_paid_posts():
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting paid media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    output=[]
    global tasks
    tasks=[]
    page_count=0
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        tasks.append(asyncio.create_task(scrape_all_paid(job_progress)))
        
        page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
        while len(tasks)!=0:
            for coro in asyncio.as_completed(tasks):
                result=await coro or []
                page_count=page_count+1
                overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                output.extend(result)
            tasks=list(filter(lambda x:x.done()==False,tasks))
        overall_progress.remove_task(page_task)  
    log.debug(f"[bold]Paid Post count without Dupes[/bold] {len(output)} found")
    # set purchash check values during scan
    # cache.set(f"purchased_all",output,expire=constants.)
    return output


@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_all_paid(job_progress,offset=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list."""
    global sem
    global tasks
    media = None
    offset = 0
    headers = auth.make_headers(auth.read_auth())
    attempt.set(attempt.get(0) + 1)
    
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    async with httpx.AsyncClient(http2=True, headers=headers, follow_redirects=True) as c:
        auth.add_cookies(c)
        url = constants.purchased_contentALL.format(offset)
        offset += 10
        c.headers.update(auth.create_sign(url, headers))
        r = await c.get(url, timeout=None)
        sem.release()
    if not r.is_error:
        attempt.set(0)
        # if "hasMore" in r.json() and r.json()['hasMore']:
        #     tasks.append(asyncio.create_task(scrape_paid(offset=offset)))
        media=list(filter(lambda x:isinstance(x,list),r.json().values()))[0]
        job_progress.remove_task(task)

    else:
        log.debug(f"[bold]paid request status code:[/bold]{r.status_code}")
        log.debug(f"[bold]paid response:[/bold] {r.content.decode()}")
        log.debug(f"[bold]paid headers:[/bold] {r.headers}")
        job_progress.remove_task(task)
        r.raise_for_status()
    return media




