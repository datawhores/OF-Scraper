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
import ssl
import certifi
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

async def get_stories_post(model_id):
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting story media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    output=[]
    page_count=0
    global tasks
    tasks=[]
    with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=constants.API_REEQUEST_TIMEOUT, connect=None,
                      sock_connect=None, sock_read=None),connector = aiohttp.TCPConnector(limit=1)) as c: 
            tasks.append(asyncio.create_task(scrape_stories(c,model_id,job_progress)))
            page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
            while len(tasks)!=0:
                for coro in asyncio.as_completed(tasks):
                    result=await coro or []
                    page_count=page_count+1
                    overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                    output.extend(result)
                tasks=list(filter(lambda x:x.done()==False,tasks))
            overall_progress.remove_task(page_task)  
    log.trace("stories raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo stories: {str(x)}",output)))))
    log.debug(f"[bold]stories+highlight Count without Dupes[/bold] {len(output)} found")
    return output


@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_stories( c,user_id,job_progress) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    stories=None
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    headers=auth.make_headers(auth.read_auth())
  

    url= constants.highlightsWithAStoryEP.format(user_id)
    r=await c.request("get",url ,ssl=ssl.create_default_context(cafile=certifi.where()),cookies=auth.add_cookies(),headers=auth.create_sign(url, headers))
    
    sem.release()
    if  r.ok:
        attempt.set(0)
        stories =await r.json()
        log.debug(f"stories: -> found stories ids {list(map(lambda x:x.get('id'),stories))}") 
        log.trace("stories: -> stories raw {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"scrapeinfo stories: {str(x)}",stories)))))
        job_progress.remove_task(task)

    else:
        job_progress.remove_task(task)
        r.raise_for_status()
    return   stories 






async def get_highlight_post(model_id):

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=constants.API_REEQUEST_TIMEOUT, connect=None,
                      sock_connect=None, sock_read=None),connector = aiohttp.TCPConnector(limit=1)) as c: 
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting highlight list...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))

        output=[]

        page_count=0
        global tasks
        tasks=[]    
        with Live(progress_group, refresh_per_second=5,console=console.shared_console):
        
                tasks.append(asyncio.create_task(scrape_highlight_list(c,model_id,job_progress)))
                page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
                while len(tasks)!=0:
                    for coro in asyncio.as_completed(tasks):
                        result=await coro or []
                        page_count=page_count+1
                        overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                        output.extend(result)
                    tasks=list(filter(lambda x:x.done()==False,tasks))
                
          
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting highlight...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))
        with Live(progress_group, refresh_per_second=5,console=console.shared_console):


            output2=[]
            page_count=0
            tasks=[]
                
            [tasks.append(asyncio.create_task(scrape_highlights(c,i,job_progress))) for i in output]
            page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True) 
            while len(tasks)!=0:
                for coro in asyncio.as_completed(tasks):
                    result=await coro or []
                    page_count=page_count+1
                    overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                    output2.extend(result)
                tasks=list(filter(lambda x:x.done()==False,tasks))

    # log.trace("stories+highlight raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo stories+highlight: {str(x)}",output)))))
    # log.debug(f"[bold]stories+highlight Count without Dupes[/bold] {len(output)} found")
    return output2


@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_highlight_list( c,user_id,job_progress,offset=0) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    headers=auth.make_headers(auth.read_auth())
  

    url= constants.highlightsWithStoriesEP.format(user_id,offset)

    r=await c.request("get",url ,ssl=ssl.create_default_context(cafile=certifi.where()),cookies=auth.add_cookies(),headers=auth.create_sign(url , headers))
    
    # highlights_, stories
    sem.release()
    if  r.ok:
        attempt.set(0)
        resp_data=(await r.json())
        log.trace(f"highlights list: -> found highlights list data {resp_data}")
        data=get_highlightList(resp_data)
        log.debug(f"highlights list: -> found list ids {data}")
    
        job_progress.remove_task(task)
        if resp_data.get("hasMore"):
            tasks.append(asyncio.create_task(scrape_highlight_list(c,user_id,job_progress,offset+len(data))))



    else:
        job_progress.remove_task(task)
        r.raise_for_status()
    return  data



@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_highlights( c,id,job_progress) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    headers=auth.make_headers(auth.read_auth())
  

    url= constants.storyEP.format(id)

    r=await c.request("get",url ,ssl=ssl.create_default_context(cafile=certifi.where()),cookies=auth.add_cookies(),headers=auth.create_sign(url , headers))
    
    # highlights_, stories
    sem.release()
    if  r.ok:
        attempt.set(0)
        resp_data=(await r.json())
        log.trace(f"highlights: -> found highlights data {resp_data}")
        log.debug(f"highlights: -> found ids {list(map(lambda x:x.get('id'),resp_data['stories']))}")
        job_progress.remove_task(task)
    else:
        job_progress.remove_task(task)
        r.raise_for_status()
    return resp_data['stories']




def get_highlightList(data):
    for ele in list(filter(lambda x:isinstance(x,list),data.values())):
        if len(list(filter(lambda x:isinstance(x.get("id"),int) and data.get("hasMore")!=None,ele)))>0:
               return list(map(lambda x:x.get("id"),ele))
    return []


    



def get_individual_highlight(id,client=None):
    headers = auth.make_headers(auth.read_auth())
    url=constants.highlightSPECIFIC.format(id)
    client.headers.update(auth.create_sign(url, headers))
    r=client.get(url)
    if not r.is_error:
        return r.json()
    log.debug(f"{r.status_code}")
    log.debug(f"{r.content.decode()}")

def get_individual_stories(id,client=None):
    headers = auth.make_headers(auth.read_auth())
    url=constants.storiesSPECIFIC.format(id)
    client.headers.update(auth.create_sign(url, headers))
    r=client.get(url)
    if not r.is_error:
        return r.json()
    log.debug(f"{r.status_code}")
    log.debug(f"{r.content.decode()}")



