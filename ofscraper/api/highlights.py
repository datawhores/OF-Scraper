r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
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
import ofscraper.constants as c
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.console as console
import ofscraper.classes.sessionbuilder as sessionbuilder

log=logging.getLogger("shared")
sem = semaphoreDelayed(1)
attempt = contextvars.ContextVar("attempt")

async def get_stories_post(model_id):
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting story media...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))

        output=[]
        page_count=0
        global tasks
        global new_tasks
        tasks=[]
        new_tasks=[]
        with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()):
                async with sessionbuilder.sessionBuilder() as c:
                    tasks.append(asyncio.create_task(scrape_stories(c,model_id,job_progress)))
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
                            output.extend(result)
                        tasks = list(pending)
                        tasks.extend(new_tasks)
                        new_tasks=[]
                overall_progress.remove_task(page_task)
        log.trace("stories raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo stories: {str(x)}",output)))))
        log.debug(f"[bold]stories Count with Dupes[/bold] {len(output)} found")
        outdict={}
        for ele in output:
            outdict[ele["id"]]=ele
        log.debug(f"[bold]stories Count with Dupes[/bold] {len(list(outdict.values()))} found")
        return list(outdict.values())


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_stories( c,user_id,job_progress) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    stories=None
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES} : user id -> {user_id}",visible=True)
    async with c.requests(url=constants.highlightsWithAStoryEP.format(user_id))() as r:
        sem.release()
        if r.ok:
            attempt.set(0)
            stories =await r.json_()
            log.debug(f"stories: -> found stories ids {list(map(lambda x:x.get('id'),stories))}") 
            log.trace("stories: -> stories raw {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"scrapeinfo stories: {str(x)}",stories)))))
            job_progress.remove_task(task)
        else:
            log.debug(f"[bold]stories response status code:[/bold]{r.status}")
            log.debug(f"[bold]stories response:[/bold] {await r.text_()}")
            log.debug(f"[bold]stories headers:[/bold] {r.headers}")
            r.raise_for_status()
        return   stories 
        
    
  
    r






async def get_highlight_post(model_id):
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        async with sessionbuilder.sessionBuilder() as c:
            overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting highlight list...\n{task.description}"))
            job_progress=Progress("{task.description}")
            progress_group = Group(
            overall_progress,
            Panel(Group(job_progress)))

            output=[]

            page_count=0
            global tasks
            global new_tasks
            tasks=[]
            new_tasks=[] 
            with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()):
            
                    tasks.append(asyncio.create_task(scrape_highlight_list(c,model_id,job_progress)))
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
                            output.extend(result)
                        tasks = list(pending)
                        tasks.extend(new_tasks)
                        new_tasks=[]
                    overall_progress.remove_task(page_task)
                    
            
            overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting highlight...\n{task.description}"))
            job_progress=Progress("{task.description}")
            progress_group = Group(
            overall_progress,
            Panel(Group(job_progress)))
            with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()):


                output2=[]
                page_count=0
                tasks=[]
                new_tasks=[]
                    
                [tasks.append(asyncio.create_task(scrape_highlights(c,i,job_progress))) for i in output]
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
                        output2.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks=[]

            

        log.trace("highlight raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo heighlight: {str(x)}",output)))))
        log.debug(f"[bold]highlight Count with Dupes[/bold] {len(output2)} found")
        outdict={}
        for ele in output2:
            outdict[ele["id"]]=ele
        log.debug(f"[bold]highlight Count with Dupes[/bold] {len(list(outdict.values()))} found")
        return list(outdict.values())



@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_highlight_list( c,user_id,job_progress,offset=0) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
    async with c.requests(url=constants.highlightsWithStoriesEP.format(user_id,offset))() as r:
        sem.release()
        if r.ok:
            attempt.set(0)
            resp_data=(await r.json_())
            log.trace(f"highlights list: -> found highlights list data {resp_data}")
            data=get_highlightList(resp_data)
            log.debug(f"highlights list: -> found list ids {data}")
    
        else:
            log.debug(f"[bold]highlight list response status code:[/bold]{r.status}")
            log.debug(f"[bold]highlight list response:[/bold] {await r.text_()}")
            log.debug(f"[bold]highlight list headers:[/bold] {r.headers}")
    return  data



@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_highlights( c,id,job_progress) -> list:
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES} highlights id -> {id}",visible=True)
    async with c.requests(url=constants.storyEP.format(id))() as r:
        sem.release()
        if r.ok:
            attempt.set(0)
            resp_data=(await r.json_())
            log.trace(f"highlights: -> found highlights data {resp_data}")
            log.debug(f"highlights: -> found ids {list(map(lambda x:x.get('id'),resp_data['stories']))}")
            job_progress.remove_task(task)
        else:
            log.debug(f"[bold]highlight status code:[/bold]{r.status}")
            log.debug(f"[bold]highlight response:[/bold] {r.text_()}")
            log.debug(f"[bold]highlight headers:[/bold] {r.headers}")
    return resp_data['stories']




def get_highlightList(data):
    for ele in list(filter(lambda x:isinstance(x,list),data.values())):
        if len(list(filter(lambda x:isinstance(x.get("id"),int) and data.get("hasMore")!=None,ele)))>0:
               return list(map(lambda x:x.get("id"),ele))
    return []


    






def get_individual_highlights(id,c=None):
    return get_individual_stories(id,c)
    # with c.requests(constants.highlightSPECIFIC.format(id))() as r:
    #     if r.ok:
    #         log.trace(f"highlight raw highlight individua; {r.json()}")
    #         return r.json()
    #     else:
    #         log.debug(f"[bold]highlight response status code:[/bold]{r.status}")
    #         log.debug(f"[bold]highlightresponse:[/bold] {r.text_()}")
    #         log.debug(f"[bold]highlight headers:[/bold] {r.headers}")






def get_individual_stories(id,c=None):
    with c.requests(constants.storiesSPECIFIC.format(id))() as r:
        if r.ok:
            log.trace(f"highlight raw highlight individua; {r.json_()}")
            return r.json()
        else:
            log.debug(f"[bold]highlight response status code:[/bold]{r.status}")
            log.debug(f"[bold]highlightresponse:[/bold] {r.text_()}")
            log.debug(f"[bold]highlight headers:[/bold] {r.headers}")


