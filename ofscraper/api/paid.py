r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
from concurrent.futures import ThreadPoolExecutor
import logging
import asyncio
import contextvars
from rich.progress import Progress
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn
)
from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type
from rich.panel import Panel
from rich.console import Group
from rich.live import Live
from rich.style import Style
import ofscraper.constants as constants
from ..utils.paths import getcachepath
import ofscraper.utils.console as console
import ofscraper.constants as constants
from diskcache import Cache
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.utils.args as args_ 
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.config as config_



paid_content_list_name = 'list'
log=logging.getLogger("shared")

sem = semaphoreDelayed(constants.MAX_SEMAPHORE)

attempt = contextvars.ContextVar("attempt")









async def get_paid_posts(username,model_id):
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting paid media...\n{task.description}"))
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
                tasks.append(asyncio.create_task(scrape_paid(c,username,job_progress)))
            
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
        for post in output:
            outdict[post["id"]]=post
        log.trace("paid raw unduped {posts}".format(posts=  "\n\n".join(list(map(lambda x:f"undupedinfo paid: {str(x)}",  outdict.values())))))
        cache.set(f"purchased_check_{model_id}", list(outdict.values()),expire=constants.CHECK_EXPIRY)
        cache.close()
        return  list(outdict.values())
        
    


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_paid(c,username,job_progress,offset=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list."""
    global sem
    global tasks
    media = None
    attempt.set(attempt.get(0) + 1)
    try:
        task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}",visible=True)
        await sem.acquire()
        async with c.requests(url=constants.purchased_contentEP.format(offset,username))() as r:
            sem.release()
            if r.ok:
                data=await r.json_()
                log.trace("paid raw {posts}".format(posts=  data))
                attempt.set(0)
                media=list(filter(lambda x:isinstance(x,list),data.values()))[0]
                log.debug(f"offset:{offset} -> media found {len(media)}")
                log.debug(f"offset:{offset} -> hasmore value in json {data.get('hasMore','undefined') }")
                log.debug(f"offset:{offset} -> found paid content ids {list(map(lambda x:x.get('id'),media))}")
                if  data.get("hasMore"):
                    offset += len(media)
                    new_tasks.append(asyncio.create_task(scrape_paid(c,username,job_progress,offset=offset)))
                job_progress.remove_task(task)

            else:
                log.debug(f"[bold]paid response status code:[/bold]{r.status}")
                log.debug(f"[bold]paid response:[/bold] {await r.text_()}")
                log.debug(f"[bold]paid headers:[/bold] {r.headers}")
                job_progress.remove_task(task)
                r.raise_for_status()
    except Exception as E:
        raise E
    finally:
        sem.release()
    return media





async def get_all_paid_posts():
    with  ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
        overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting all paid media...\n{task.description}"))
        job_progress=Progress("{task.description}")
        progress_group = Group(
        overall_progress,
        Panel(Group(job_progress)))

        output=[]
        min_posts=100
        global tasks
        global new_tasks
        tasks=[]
        new_tasks=[]
        page_count=0
        with Live(progress_group, refresh_per_second=5,console=console.get_shared_console()):
            async with sessionbuilder.sessionBuilder() as c:
                if not args_.getargs().no_cache:allpaid=cache.get(f"purchased_all",default=[])
                else:allpaid=[]
                log.debug(f"[bold]All Paid Cache[/bold] {len(allpaid)} found")

                if len(allpaid)>min_posts:
                    splitArrays=[i for i in range(0, len(allpaid), min_posts)]
                    #use the previous split for timesamp
                    tasks.append(asyncio.create_task(scrape_all_paid(c,job_progress,offset=0,count=0,required=0)))
                    [ tasks.append(asyncio.create_task(scrape_all_paid(c,job_progress,count=0,required=0,offset=splitArrays[i])))
                    for i in range(1,len(splitArrays))]
                    # keeping grabbing until nothign left
                    tasks.append(asyncio.create_task(scrape_all_paid(c,job_progress,offset=len(allpaid))))
                else:
                    tasks.append(asyncio.create_task(scrape_all_paid(c,job_progress)))
                    
                
                
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
        log.debug(f"[bold]Paid Post count with Dupes[/bold] {len(output)} found")
        for post in output:
            outdict[post["id"]]=post
            
        log.debug(f"[bold]Paid Post count[/bold] {len(outdict.values())} found")
        cache.set(f"purchased_all",list(map(lambda x:x.get("id"),list(outdict.values()))),expire=constants.RESPONSE_EXPIRY)
        cache.close()
        #filter at user level
        return output


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_all_paid(c,job_progress,offset=0,count=0,required=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list."""
    global sem
    global new_tasks
    media = None
    attempt.set(attempt.get(0) + 1)
    await sem.acquire()
    task=job_progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES} offset={offset}",visible=True)
    async with c.requests(url= constants.purchased_contentALL.format(offset))() as r:
        sem.release()
        if r.ok:
            attempt.set(0) 
            log_id=f"offset {offset or 0}:"
            data=await r.json_()   
            job_progress.remove_task(task)
            media=list(filter(lambda x:isinstance(x,list),data.values()))[0]
            if not data.get("hasMore"):
                media=[]
            if not media:
                media=[]
            if len(media)==0:
                log.debug(f"{log_id} -> number of post found 0")
            elif len(media)>0:
                log.debug(f"{log_id} -> number of post found {len(media)}")
                log.debug(f"{log_id} -> first date {media[0].get('createdAt') or media[0].get('postedAt')}")
                log.debug(f"{log_id} -> last date {media[-1].get('createdAt') or media[-1].get('postedAt')}")
                log.debug(f"{log_id} -> found paid content ids {list(map(lambda x:x.get('id'),media))}")

                if required==0:
                    attempt.set(0)
                    new_tasks.append(asyncio.create_task(scrape_all_paid(c,job_progress,offset=offset+len(media))))

                elif len(count)<len(required):
                    new_tasks.append(asyncio.create_task(scrape_all_paid(c,job_progress,offset=offset+len(media),required=required,count=count+len(media))))


            

        else:
            log.debug(f"[bold]paid response status code:[/bold]{r.status}")
            log.debug(f"[bold]paid response:[/bold] {await r.text_()}")
            log.debug(f"[bold]paid headers:[/bold] {r.headers}")
            job_progress.remove_task(task)
            r.raise_for_status()
    return media




