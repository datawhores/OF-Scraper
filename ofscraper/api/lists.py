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
import ofscraper.constants as constants
import ofscraper.utils.console as console
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args as args_
from ofscraper.utils.run_async import run

log=logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")

sem = semaphoreDelayed(constants.MAX_SEMAPHORE)
@run
async def get_otherlist():
    out=[]
    if len(args_.getargs().user_list)>=2 or constants.OFSCRAPER_RESERVED_LIST not in args_.getargs().user_list:
        out.extend(await get_lists())
    out=list(filter(lambda x:x.get("name").lower() in args_.getargs().user_list,out))
    log.debug(f"User lists found on profile {list(map(lambda x:x.get('name').lower(),out))}")
    return await get_list_users(out)

@run
async def get_blacklist():
    out=[]
    if len(args_.getargs().black_list)>=1:
        out.extend(await get_lists())
    out=list(filter(lambda x:x.get("name").lower() in args_.getargs().black_list,out))
    log.debug(f"Black lists found on profile {list(map(lambda x:x.get('name').lower(),out))}")
    names= list(await get_list_users(out))
    return set(list(map(lambda x:x["id"],names)))
      


async def get_lists():
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting lists...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))

        output=[]
        global tasks
        global new_tasks
        tasks=[]
        new_tasks=[]
        page_count=0
        with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()):
            async with sessionbuilder.sessionBuilder() as c: 
                    tasks.append(asyncio.create_task(scrape_lists(c,job_progress)))
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
        log.trace("list unduped {posts}".format(posts= "\n\n".join(map(lambda x:f" list data raw:{x}",output))))
        log.debug(f"[bold]lists name count without Dupes[/bold] {len(output)} found")
        return output    

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_lists(c,job_progress,offset=0):
    global sem
    global tasks
    attempt.set(attempt.get(0) + 1)
    
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES} {offset}",visible=True)
    async with c.requests(url=constants.listEP.format(offset))() as r:
        sem.release()
        if r.ok:
            data=await r.json_()
            attempt.set(0)
            out_list=data["list"] or []
            log.debug(f"offset:{offset} -> lists names found {len(out_list)}")
            log.debug(f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }")
            log.trace("offset:{offset} -> label names raw: {posts}".format(offset=offset,posts=data))  

            if data.get("hasMore"):
                offset = data.get("nextOffset")
                new_tasks.append(asyncio.create_task(scrape_lists(c,job_progress,offset=offset)))
            job_progress.remove_task(task)
            return out_list

        else:
            log.debug(f"[bold]lists response status code:[/bold]{r.status}")
            log.debug(f"[bold]lists response:[/bold] {await r.text_()}")
            log.debug(f"[bold]lists headers:[/bold] {r.headers}")
            job_progress.remove_task(task)
            r.raise_for_status()


async def get_list_users(lists):
     with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting users from lists (this may take awhile)...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))

        output=[]
        global tasks
        global new_tasks
        tasks=[]
        new_tasks=[]
        page_count=0
        with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()):
            async with sessionbuilder.sessionBuilder() as c:
                [tasks.append(asyncio.create_task(scrape_list(c,id,job_progress)))
                    for id in lists]
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
        outdict={}
        for ele in output:
            outdict[ele["id"]]=ele
        log.trace("users found {users}".format(users=  "\n\n".join(list(map(lambda x:f"label post joined: {str(x)}",outdict.values())))))
        log.debug(f"[bold]users count without Dupes[/bold] {len(outdict.values())} found")
        return outdict.values()

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_list(c,item,job_progress,offset=0):
    global sem
    global tasks
    users = None
    attempt.set(attempt.get(0) + 1)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES} : offset -> {offset} + label -> {item.get('name')}",visible=True)
    
    async with c.requests(url=constants.listusersEP.format(item.get("id"),offset))() as r:
        sem.release()
        log_id=f"offset:{offset} list:{item.get('name')} =>"
        if r.ok:
            data=await r.json_()
            attempt.set(0)
            users=data.get("list") or []
            log.debug(f"{log_id} -> names found {len(users)}")
            log.debug(f"{log_id}  -> hasMore value in json {data.get('hasMore','undefined') }")
            log.debug(f"usernames {log_id} : usernames retrived -> {list(map(lambda x:x.get('username'),users))}")   
            log.trace("offset: {offset} list: {item} -> {posts}".format(item=item.get("name"),offset=offset,posts= "\n\n".join(list(map(lambda x:f"scrapeinfo list {str(x)}",users)))))  
            if data.get("hasMore"):
                offset += len(users)
                new_tasks.append(asyncio.create_task(scrape_list(c, item,job_progress,offset=offset)))
            job_progress.remove_task(task)
 
        else:
            log.debug(f"[bold]labelled posts response status code:[/bold]{r.status}")
            log.debug(f"[bold]labelled posts response:[/bold] {await r.text_()}")
            log.debug(f"[bold]labelled posts headers:[/bold] {r.headers}")

            job_progress.remove_task(task)
            r.raise_for_status()
    return users
