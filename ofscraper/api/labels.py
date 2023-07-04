r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import aiohttp
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

async def get_labels(model_id):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting labels...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    output=[]
    global tasks
    tasks=[]
    page_count=0
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=constants.API_REEQUEST_TIMEOUT, connect=None,
                      sock_connect=None, sock_read=None),connector = aiohttp.TCPConnector(limit=constants.MAX_SEMAPHORE)) as c: 

            tasks.append(asyncio.create_task(scrape_labels(c,model_id,job_progress)))

            page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
            while len(tasks)!=0:
                for coro in asyncio.as_completed(tasks):
                    result=await coro or []
                    page_count=page_count+1
                    overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                    output.extend(result)
                tasks=list(filter(lambda x:x.done()==False,tasks))
            overall_progress.remove_task(page_task)  
    log.debug(f"[bold]Labels count without Dupes[/bold] {len(output)} found")

    return output    

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_labels(c,model_id,job_progress,offset=0):
    global sem
    global tasks
    labels = None
    attempt.set(attempt.get(0) + 1)
    url = constants.labelsEP.format(model_id, offset)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    headers=auth.make_headers(auth.read_auth())
    headers=auth.create_sign(url, headers)
    async with c.request("get",url,verify_ssl=False,cookies=auth.add_cookies_aio(),headers=headers) as r:
        sem.release()
        if r.ok:
            data=await r.json()
            attempt.set(0)
            labels=list(filter(lambda x:isinstance(x,list),data.values()))[0]
            log.debug(f"offset:{offset} -> labels found {len(labels)}")
            log.debug(f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }")
            if data.get("hasMore"):
                offset = data.get("nextOffset")
                tasks.append(asyncio.create_task(scrape_labels(c, model_id,job_progress,offset=offset)))
            job_progress.remove_task(task)

        else:
            log.debug(f"[bold]labels request status code:[/bold]{r.status}")
            log.debug(f"[bold]labels response:[/bold] {await r.text()}")
            log.debug(f"[bold]labels headers:[/bold] {r.headers}")
            job_progress.remove_task(task)
            r.raise_for_status()

    return labels


async def get_labelled_posts(labels, username):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting labels...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    output={}
    global tasks
    tasks=[]
    page_count=0
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=constants.API_REEQUEST_TIMEOUT, connect=None,
                      sock_connect=None, sock_read=None),connector = aiohttp.TCPConnector(limit=constants.MAX_SEMAPHORE)) as c: 

            [tasks.append(asyncio.create_task(scrape_labelled_posts(c,label,username,job_progress)))
                for label in labels]

            page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
            while len(tasks)!=0:
                for coro in asyncio.as_completed(tasks):
                    label, posts = await coro
                    page_count=page_count+1
                    overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                    
                    label_id_ = label['id']
                    label_ = output.get(label_id_, None)
                    if not label_:
                        output[label_id_] = label
                        output[label_id_]['posts'] = posts
                    else:
                        output[label_id_]['posts'].extend(posts)

                tasks=list(filter(lambda x:x.done()==False,tasks))
            overall_progress.remove_task(page_task)  
    log.debug(f"[bold]Labels count without Dupes[/bold] {len(output)} found")

    return list(output.values())

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_labelled_posts(c,label,model_id,job_progress,offset=0):
    global sem
    global tasks
    posts = None
    attempt.set(attempt.get(0) + 1)
    url = constants.labelledPostsEP.format(model_id, offset, label['id'])
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    headers=auth.make_headers(auth.read_auth())
    headers=auth.create_sign(url, headers)
    async with c.request("get",url,verify_ssl=False,cookies=auth.add_cookies_aio(),headers=headers) as r:
        if r.ok:
            data=await r.json()
            attempt.set(0)
            posts=list(filter(lambda x:isinstance(x,list),data.values()))[0]
            log.debug(f"offset:{offset} -> labelled posts found {len(posts)}")
            log.debug(f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }")
            if data.get("hasMore"):
                offset += len(posts)
                tasks.append(asyncio.create_task(scrape_labelled_posts(c, label, model_id,job_progress,offset=offset)))
            job_progress.remove_task(task)

        else:
            log.debug(f"[bold]labelled posts request status code:[/bold]{r.status}")
            log.debug(f"[bold]labelled posts response:[/bold] {await r.text()}")
            log.debug(f"[bold]labelled posts headers:[/bold] {r.headers}")
            job_progress.remove_task(task)
            r.raise_for_status()

    return label, posts
