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

from collections import abc
from functools import singledispatch,partial
import math
import os
import pathlib
import multiprocess
import time
import platform
import shutil
import traceback
import random
import re
import threading
import logging
import logging.handlers
import contextvars
import json
import subprocess
import aiofiles
from rich.progress import (
    Progress,
    TimeElapsedColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TextColumn,
    TaskProgressColumn,
    BarColumn,
    TimeRemainingColumn
)

from rich.live import Live
from rich.panel import Panel
from rich.console import Group
from rich.table import Column
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH
import arrow
from bs4 import BeautifulSoup


from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type
import more_itertools
import aioprocessing
import psutil
from diskcache import Cache
import ofscraper.utils.config as config_
import ofscraper.db.operations as operations
import ofscraper.utils.paths as paths
import ofscraper.utils.auth as auth
import ofscraper.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logger as logger
import ofscraper.utils.console as console
import ofscraper.utils.stdout as stdout
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
import ofscraper.utils.exit as exit
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.classes.placeholder as placeholder
import ofscraper.classes.sessionbuilder as sessionbuilder
from   ofscraper.classes.multiprocessprogress import MultiprocessProgress as progress 
import ofscraper.utils.system as system
from ofscraper.utils.run_async import run

from aioprocessing import AioPipe
platform_name=platform.system()
if platform_name== 'Windows':
    from win32_setctime import setctime 
 # pylint: disable=import-errorm
 
#main thread queues
logqueue_=logger.queue_



@singledispatch
def sem_wrapper(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
         return sem_wrapper(args[0])
    return sem_wrapper(**kwargs)

@sem_wrapper.register
def _(input_sem: semaphoreDelayed):
    return partial(sem_wrapper,input_sem=input_sem)


@sem_wrapper.register
def _(func:abc.Callable,input_sem:None|semaphoreDelayed=None):
    async def inner(*args,input_sem=input_sem,**kwargs):
        if input_sem==None:input_sem=sem 
        await input_sem.acquire()
        try:  
            return await func(*args,**kwargs) 
        except Exception as E:
            raise E  
        finally:
            input_sem.release()  
    return inner


def reset_globals():
    #reset globals

    global total_bytes_downloaded
    total_bytes_downloaded = 0
    global total_bytes
    total_bytes=0
    global photo_count
    photo_count = 0
    global video_count
    video_count = 0
    global audio_count
    audio_count=0
    global skipped
    skipped = 0
    global forced_skipped
    forced_skipped=0
    global data
    data=0
    global total_data
    total_data=0
    global desc
    desc = 'Progress: ({p_count} photos, {v_count} videos, {a_count} audios, {forced_skipped} skipped, {skipped} failed || {sumcount}/{mediacount}||{data}/{total})'   
    global count_lock
    count_lock=aioprocessing.AioLock()
    global chunk_lock
    chunk_lock=aioprocessing.AioLock()
    global dirSet
    dirSet=set()
    global dir_lock
    dir_lock=aioprocessing.AioLock()


def process_dicts(username,model_id,filtered_medialist):
    log=logging.getLogger("shared")
    try:
        reset_globals()
        random.shuffle(filtered_medialist)
        with multiprocess.Manager() as manager:
            mediasplits=get_mediasplits(filtered_medialist)
            num_proc=len(mediasplits)
            split_val=min(4,num_proc)
            log.debug(f"Number of process {num_proc}")
            connect_tuples=[AioPipe() for _ in range(num_proc)]
            shared=list(more_itertools.chunked([i for i in range(num_proc)],split_val))
            #shared with other process + main
            logqueues_=[ manager.Queue() for _ in range(len(shared))]
            #other logger queues
            otherqueues_=[manager.Queue()  for _ in range(len(shared))]

            
            #start stdout/main queues consumers
            logthreads=[logger.start_stdout_logthread(input_=logqueues_[i],name=f"ofscraper_{model_id}_{i+1}",count=len(shared[i])) for i in range(len(shared))]
  
            processes=[ aioprocessing.AioProcess(target=process_dict_starter, args=(username,model_id,mediasplits[i],logqueues_[i//split_val],otherqueues_[i//split_val],connect_tuples[i][1])) for i in range(num_proc)]
            [process.start() for process in processes]
            downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars
            job_progress=progress(TextColumn("{task.description}",table_column=Column(ratio=2)),BarColumn(),
                TaskProgressColumn(),TimeRemainingColumn(),TransferSpeedColumn(),DownloadColumn())      
            overall_progress=Progress(  TextColumn("{task.description}"),
            BarColumn(),TaskProgressColumn(),TimeElapsedColumn())
            progress_group = Group(overall_progress,Panel(Group(job_progress,fit=True)))
            task1 = overall_progress.add_task(desc.format(p_count=photo_count, v_count=video_count,a_count=audio_count, skipped=skipped,mediacount=len(filtered_medialist), sumcount=video_count+audio_count+photo_count+skipped,forced_skipped=forced_skipped,data=data,total=total_data), total=len(filtered_medialist),visible=True)
            progress_group.renderables[1].height=max(15,console.get_shared_console().size[1]-2) if downloadprogress else 0
            with stdout.lowstdout():
                with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.get_shared_console()):
                    queue_threads=[threading.Thread(target=queue_process,args=(connect_tuples[i][0],overall_progress,job_progress,task1,len(filtered_medialist)),daemon=True) for i in range(num_proc)]
                    [thread.start() for thread in queue_threads]
                    while len(list(filter(lambda x:x.is_alive(),logthreads)))>0: 
                        for thread in list(filter(lambda x:x.is_alive(),logthreads)):
                            thread.join(timeout=.1)
                        time.sleep(.5)
        while len(list(filter(lambda x:x.is_alive(),queue_threads)))>0: 
            for thread in list(filter(lambda x:x.is_alive(),queue_threads)):
                thread.join(timeout=.1)
            time.sleep(.5)
        while len(list(filter(lambda x:x.is_alive(),processes)))>0: 
            for process in list(filter(lambda x:x.is_alive(),process)):
                process.join(timeout=.1)
            time.sleep(.5)
        # [process.terminate() for process in processes]
        overall_progress.remove_task(task1)
        progress_group.renderables[1].height=0
        setDirectoriesDate()  
    except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    [process.terminate() for process in processes] 
                    manager.shutdown()
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                    with exit.DelayedKeyboardInterrupt():
                        raise E
            except:
                with exit.DelayedKeyboardInterrupt():
                    raise E
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                [process.terminate() for process in processes]
                manager.shutdown()
                raise E
        except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    raise E
        except Exception:
            with exit.DelayedKeyboardInterrupt():
                raise E
    log.error(f'[bold]{username}[/bold] ({photo_count+audio_count+video_count} downloads total [{video_count} videos, {audio_count} audios, {photo_count} photos],  {forced_skipped} skipped, {skipped} failed)' )
    cache = Cache(paths.getcachepath())
    cache.close()
    return photo_count,video_count,audio_count,forced_skipped,skipped


def queue_process(pipe_,overall_progress,job_progress,task1,total):
    count=0
    downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars
        #shared globals
    global total_bytes_downloaded
    global total_bytes
    global video_count
    global audio_count
    global photo_count
    global skipped
    global forced_skipped
    global data
    global total_data
    global desc

    while True:
        if count==1 or overall_progress.tasks[task1].total==overall_progress.tasks[task1].completed:
            break
        results = pipe_.recv()
        if not isinstance(results,list):
            results=[results]

        for result in results:
            if result is None:
                count=count+1
                continue 
            if isinstance(result,dict) and not downloadprogress:
                continue
            if isinstance(result,set):
                addGlobalDir(result)
                continue
            if isinstance(result,dict):
                job_progress_helper(job_progress,result)
                continue
            media_type, num_bytes_downloaded,total_size = result
            with count_lock:
                total_bytes_downloaded=total_bytes_downloaded+num_bytes_downloaded
                total_bytes=total_bytes+total_size
                
                data = convert_num_bytes(total_bytes_downloaded)
                total_data=convert_num_bytes(total_bytes)
                if media_type == 'images':
                    photo_count += 1 

                elif media_type == 'videos':
                    video_count += 1
                elif media_type == 'audios':
                    audio_count += 1
                elif media_type == 'skipped':
                    skipped += 1
                elif media_type =='forced_skipped':
                    forced_skipped+=1
                overall_progress.update(task1,description=desc.format(
                            p_count=photo_count, v_count=video_count, a_count=audio_count,skipped=skipped,forced_skipped=forced_skipped, data=data,total=total_data,mediacount=total, sumcount=video_count+audio_count+photo_count+skipped+forced_skipped), refresh=True, completed=video_count+audio_count+photo_count+skipped+forced_skipped)     


def get_mediasplits(medialist):
    user_count=config_.get_threads(config_.read_config() or args_.getargs().downloadthreads)
    final_count=min(user_count,system.getcpu_count(), len(medialist)//5)
    if final_count==0:final_count=1
    return more_itertools.divide(final_count, medialist   )
def process_dict_starter(username,model_id,ele,p_logqueue_,p_otherqueue_,pipe_):
    log=logger.get_shared_logger(main_=p_logqueue_,other_=p_otherqueue_,name=f"shared_{os.getpid()}")
    plat=platform.system()
    if plat=="Linux":import uvloop;asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(process_dicts_split(username,model_id,ele,log,pipe_))

def job_progress_helper(job_progress,result):
    funct={
      "add_task"  :job_progress.add_task,
      "update":job_progress.update,
      "remove_task":job_progress.remove_task
     }.get(result.pop("type"))
    if funct:
        try: 
            with chunk_lock:
                funct(*result.pop("args"),**result)
        except Exception as E:
            logging.getLogger("shared").debug(E)
def setpriority():
    os_used = platform.system() 
    process = psutil.Process(os.getpid())  # Set highest priority for the python script for the CPU
    if os_used == "Windows":  # Windows (either 32-bit or 64-bit)
        process.ionice(psutil.IOPRIO_NORMAL)
        process.nice(psutil.NORMAL_PRIORITY_CLASS)

    elif os_used == "Linux":  # linux
        process.ionice(psutil.IOPRIO_CLASS_BE)
        process.nice(5) 
    else:  # MAC OS X or other
        process.nice(10) 

@run
async def process_dicts_split(username, model_id, medialist,logCopy,pipecopy):
    global innerlog
    innerlog = contextvars.ContextVar("innerlog")
    global log 
    log=logCopy
    logCopy.debug(f"{pid_log_helper()} start inner thread for other loggers")  
    #start consumer for other
    other_thread=logger.start_other_thread(input_=logCopy.handlers[1].queue,name=str(os.getpid()),count=1)
    setpriority()
    global attempt
    attempt=contextvars.ContextVar("attempt")
    global attempt2
    attempt2=contextvars.ContextVar("attempt2")
    global total_count
    total_count=contextvars.ContextVar("total_count")   
    global total_count2
    total_count2=contextvars.ContextVar("total_count2")   
 
    medialist=list(medialist)
    # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8
    global sem
    sem = semaphoreDelayed(config_.get_download_semaphores(config_.read_config()))
    global total_sem
    total_sem= semaphoreDelayed(config_.get_download_semaphores(config_.read_config())*2)
    global maxfile_sem
    maxfile_sem = semaphoreDelayed(config_.get_maxfile_semaphores(config_.read_config()))
    global localdirSet
    localdirSet=set()
    global split_log
    split_log=logCopy
    global log_trace
    log_trace=True if "TRACE" in set([args_.getargs().log,args_.getargs().output,args_.getargs().discord]) else False
    global pipe_
    pipe_=pipecopy
    split_log.debug(f"{pid_log_helper()} starting process")
    split_log.debug(f"{pid_log_helper()} process mediasplit from total {len(medialist)}")
    global file_size_limit
    global file_size_min
    file_size_limit = args_.getargs().size_max or config_.get_filesize_limit(config_.read_config()) 
    file_size_min = args_.getargs().size_min or config_.get_filesize_min(config_.read_config()) 
    global thread
    thread=ThreadPoolExecutor(max_workers=config_.get_download_semaphores(config_.read_config())*2)   
    global cache_thread
    cache_thread=ThreadPoolExecutor(max_workers=1)   
    aws=[]

    async with sessionbuilder.sessionBuilder() as c:
        i=0
        for ele in medialist:
            aws.append(asyncio.create_task(download(c,ele ,model_id, username)))

        for coro in asyncio.as_completed(aws):
                try:
                    pack = await coro
                    log.debug(f"unpack {pack} count {len(pack)}")
                    media_type, num_bytes_downloaded=pack
                    await pipe_.coro_send(  (media_type, num_bytes_downloaded,0))
                except Exception as e:
                    split_log.traceback(e)
                    split_log.traceback(traceback.format_exc())
                    media_type = "skipped"
                    num_bytes_downloaded = 0
                    await pipe_.coro_send(  (media_type, num_bytes_downloaded,0))
            
    split_log.debug(f"{pid_log_helper()} download process thread closing")
    #send message directly
    log.handlers[0].queue.put("None")
    log.handlers[1].queue.put("None")
    other_thread.join()
    await pipe_.coro_send(localdirSet)
    await pipe_.coro_send(None)
   
 



def pid_log_helper():
    return f"PID: {os.getpid()}"  

def size_checker(path,ele,total,name=None):
    name=name or ele.filename
    if not pathlib.Path(path).exists():
        s=f"{get_medialog(ele)} {path} was not created"
        raise Exception(s)
    elif total-pathlib.Path(path).absolute().stat().st_size>500:
        s=f"{get_medialog(ele)} {name} size mixmatch target: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        raise Exception(s)
    elif (total-pathlib.Path(path).absolute().stat().st_size)<0:
        s=f"{get_medialog(ele)} {path} size mixmatch target item too large: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        raise Exception(s)
    
def check_forced_skip(ele,*args):
    total=sum(args) 
    if total==0:
        return ele.mediatype,0
    if int(file_size_limit)>0 and int(total) > int(file_size_limit): 
        innerlog.get().debug(f"{get_medialog(ele)} over size limit") 
        return 'forced_skipped', 1 
    elif int(file_size_min)>0 and int(total) < int(file_size_min): 
        innerlog.get().debug(f"{get_medialog(ele)} under size min") 
        return 'forced_skipped', 1    

async def download(c,ele,model_id,username):
    # reduce number of logs
    async with maxfile_sem:
        templog_=logger.get_shared_logger(name=str(ele.id),main_=aioprocessing.Queue(),other_=aioprocessing.Queue())
        innerlog.set(templog_)
        try:
                with paths.set_directory(placeholder.Placeholders().getmediadir(ele,username,model_id)):
                    if ele.url:
                        return await main_download_helper(c,ele,pathlib.Path(".").absolute(),username,model_id)
                    elif ele.mpd:
                        return await alt_download_helper(c,ele,pathlib.Path(".").absolute(),username,model_id)
        except Exception as e:
            innerlog.get().debug(f"{get_medialog(ele)} exception {e}")   
            innerlog.get().debug(f"{get_medialog(ele)} exception {traceback.format_exc()}")   
            raise e
        finally:
            #dump logs stdout
            log.handlers[0].queue.put(list(innerlog.get().handlers[0].queue.queue))
            # we can put into seperate otherqueue_
            log.handlers[1].queue.put(list(innerlog.get().handlers[1].queue.queue))
async def main_download_helper(c,ele,path,username,model_id): 
    path_to_file=None
    innerlog.get().debug(f"{get_medialog(ele)} Downloading with normal downloader")
    result=list(await main_download_downloader(c,ele,path,username,model_id))
    if len(result)==2 and result[-1]==0:
        if ele.id:await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
        return result
    total ,temp,path_to_file=result
    
    check1=size_checker(temp,ele,total)
    check2=check_forced_skip(ele,total)
    if check1:
        return check1
    if check2:
        return check2
    
  
    innerlog.get().debug(f"{get_medialog(ele)} {ele.filename_} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
    innerlog.get().debug(f"{get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}")   
    #move temp file
    if not path_to_file.exists():
        shutil.move(temp,path_to_file)
    elif pathlib.Path(temp).absolute().stat().st_size>=pathlib.Path(path_to_file).absolute().stat().st_size: 
        shutil.move(temp,path_to_file)
    else:
        pathlib.Path(temp).unlink(missing_ok=True)
        raise Exception(f"{get_medialog(ele)} smaller then previous file")
    addLocalDir(path)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        innerlog.get().debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        innerlog.get().debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    set_cache_helper(ele)
    return ele.mediatype,total

        



 
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def main_download_downloader(c,ele,path,username,model_id):
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    data=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,f"{ele.id}_headers"))
    await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)
    if data and data.get('content-length'):
            temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
            content_type = data.get("content-type").split('/')[-1]
            total=int(data.get('content-length'))
            filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
            path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
            resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
            check1=check_forced_skip(ele,total)
            if check1:
                return check1
            elif total==resume_size:
                return total ,temp,path_to_file
            elif total<resume_size:
                pathlib.Path(temp).unlink(missing_ok=True)
    else:
        paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part")).unlink(missing_ok=True)

    @retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
    @sem_wrapper
    async def inner(c,ele,path,username,model_id,total):
        attempt.set(attempt.get(0) + 1) 
        cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
        try:
            temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
            if total==None:temp.unlink(missing_ok=True)
            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
            resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
            if not total or total>resume_size:
                url=ele.url
                headers=None if not pathlib.Path(temp).exists() else {"Range":f"bytes={resume_size}-{total}"}
                async with c.requests(url=url,headers=headers)() as r:
                        if r.ok:
                            data=r.headers
                            await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,f"{ele.id}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))
                            total=int(data['content-length'])
                            if attempt.get()==1: await pipe_.coro_send(  (None, 0,total))
                            content_type = data.get("content-type").split('/')[-1]
                            if not content_type and ele.mediatype.lower()=="videos":content_type="mp4"
                            if not content_type and ele.mediatype.lower()=="images":content_type="jpg"
                            temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
                            filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] filename from config {filename}")
                            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] full path from config {pathlib.Path(path,f'{filename}')}")
                            path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
                            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] full path trunicated from config {path_to_file}")
                            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] passed size check with size {total}")   
                            pathstr=str(path_to_file)
                            check=check_forced_skip(ele,total)
                            if check:
                                return check
                            elif total<=resume_size:
                                return total ,temp,path_to_file
                            count=0
                            await pipe_.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                                        "total":total,"visible":False})
                            await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":resume_size,"visible":True})                        
                            
                            async with aiofiles.open(temp, 'ab') as f:                             
                                async for chunk in r.iter_chunked(constants.maxChunkSizeB):
                                    count=count+1
                                    innerlog.get().trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
                                    await f.write(chunk)
                                    if count==constants.CHUNK_ITER:await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":(pathlib.Path(temp).absolute().stat().st_size)});count=0            
                            await pipe_.coro_send({"type":"remove_task","args":(ele.id,)})                            
                        else:
                            innerlog.get().debug(f"[bold] {get_medialog(ele)} main download response status code [/bold]: {r.status}")
                            innerlog.get().debug(f"[bold] {get_medialog(ele)} main download  response text [/bold]: {await r.text_()}")
                            innerlog.get().debug(f"[bold] {get_medialog(ele)}main download headers [/bold]: {r.headers}")
                            r.raise_for_status()  
                        size_checker(temp,ele,total)
                        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.touch,f"{ele.filename}_headers",1))
            return total,temp,path_to_file
        except Exception as E:
            innerlog.get().traceback(traceback.format_exc())
            innerlog.get().traceback(E)
            raise E
        finally:
            await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)
 
        
    total=int(data.get("content-length")) if data else None
    return await inner(c,ele,path,username,model_id,total)


def get_medialog(ele):
    return f"Media:{ele.id} Post:{ele.postid}"


async def alt_download_helper(c,ele,path,username,model_id):

    innerlog.get().debug(f"{get_medialog(ele)} Downloading with protected media downloader")      
    innerlog.get().debug(f"{get_medialog(ele)} Attempting to download media {ele.filename_} with {ele.mpd}")
    filename=f'{placeholder.Placeholders().createfilename(ele,username,model_id,"mp4")}'
    innerlog.get().debug(f"{get_medialog(ele)} filename from config {filename}")
    innerlog.get().debug(f"{get_medialog(ele)} full filepath from config{pathlib.Path(path,filename)}")
    path_to_file = paths.truncate(pathlib.Path(path,filename))
    innerlog.get().debug(f"{get_medialog(ele)} full path trunicated from config {path_to_file}")
    temp_path=paths.truncate(pathlib.Path(path,f"temp_{ele.id or ele.filename_}.mp4"))
    log.debug(f"Media:{ele.id} Post:{ele.postid}  temporary path from combined audio/video {temp_path}")
    audio,video=await alt_download_preparer(ele)

    audio=await alt_download_downloader(audio,c,ele,path)
    video=await alt_download_downloader(video,c,ele,path)

    for m in [audio,video]:
        if not isinstance(m,dict):
            return m
        check1=size_checker(m["path"],ele,m["total"])
        check2=check_forced_skip(ele,m["total"])
        if check1:
            return check1
        if check2:
            return check2

        
    
    for item in [audio,video]:
        key=None
        keymode=(args_.getargs().key_mode or config_.get_key_mode(config_.read_config()) or "cdrm")
        if  keymode== "manual": key=await key_helper_manual(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="keydb":key=await key_helper_keydb(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="cdrm": key=await key_helper_cdrm(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="cdrm2": key=await key_helper_cdrm2(c,item["pssh"],ele.license,ele.id)  
        if key==None:
            innerlog.get().debug(f"{get_medialog(ele)} Could not get key")
            return "skipped",0 
        innerlog.get().debug(f"{get_medialog(ele)} got key")
        newpath=pathlib.Path(re.sub("\.part$","",str(item["path"]),re.IGNORECASE))
        innerlog.get().debug(f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}")   
        r=subprocess.run([config_.get_mp4decrypt(config_.read_config()),"--key",key,str(item["path"]),str(newpath)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if not pathlib.Path(newpath).exists():
            innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt failed")
            innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt {r.stderr.decode()}")
            innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt {r.stdout.decode()}")
        else:
            innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt success {newpath}")    
        pathlib.Path(item["path"]).unlink(missing_ok=True)
        item["path"]=newpath
    
    path_to_file.unlink(missing_ok=True)
    temp_path.unlink(missing_ok=True)
    t=subprocess.run([config_.get_ffmpeg(config_.read_config()),"-i",str(video["path"]),"-i",str(audio["path"]),"-c","copy","-movflags", "use_metadata_tags",str(temp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if t.stderr.decode().find("Output")==-1:
        innerlog.get().debug(f"{get_medialog(ele)} ffmpeg failed")
        innerlog.get().debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        innerlog.get().debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")

    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    innerlog.get().debug(f"Moving intermediate path {temp_path} to {path_to_file}")
    shutil.move(temp_path,path_to_file)
    addLocalDir(path_to_file)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        set_time(path_to_file,newDate )
        innerlog.get().debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    return ele.mediatype,audio["total"]+video["total"]

async def alt_download_preparer(ele):
    mpd=await ele.parse_mpd
    for period in mpd.periods:
                for adapt_set in filter(lambda x:x.mime_type=="video/mp4",period.adaptation_sets):             
                    kId=None
                    for prot in adapt_set.content_protections:
                        if prot.value==None:
                            kId = prot.pssh[0].pssh 
                            break
                    maxquality=max(map(lambda x:x.height,adapt_set.representations))
                    for repr in adapt_set.representations:
                        origname=f"{repr.base_urls[0].base_url_value}"
                        if repr.height==maxquality:
                            video={"origname":origname,"pssh":kId,"type":"video","name":f"tempvid_{origname}"}
                            break
                for adapt_set in filter(lambda x:x.mime_type=="audio/mp4",period.adaptation_sets):             
                    kId=None
                    for prot in adapt_set.content_protections:
                        if prot.value==None:
                            kId = prot.pssh[0].pssh 
                            logger.updateSenstiveDict(kId,"pssh_code")
                            break
                    for repr in adapt_set.representations:
                        origname=f"{repr.base_urls[0].base_url_value}"
                        audio={"origname":origname,"pssh":kId,"type":"audio","name":f"tempaudio_{origname}"}
                        break
    return audio,video
  


async def alt_download_downloader(item,c,ele,path):
    base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
    url=f"{base_url}{item['origname']}"
    innerlog.get().debug(f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}")
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    data=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,f"{item['name']}_headers"))
    await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)
    
    temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
    item['path']=temp
    if data:
        item["total"]=int(data.get("content-length"))
        check1=check_forced_skip(ele,item["total"])
        temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
        if check1:
            return check1
        elif item["total"]<resume_size:
                pathlib.Path(temp).unlink(missing_ok=True)
    else:
        paths.truncate(pathlib.Path(path,f"{item['name']}.part")).unlink(missing_ok=True)
    @retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
    @sem_wrapper    
    async def inner(item,c,ele):
        if item["type"]=="video":_attempt=attempt
        if item["type"]=="audio":_attempt=attempt2
        _attempt.set(_attempt.get(0)+1) 
        cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
        try:
            total=item.get("total")
            if total==None:temp.unlink(missing_ok=True)
            resume_size=0 if not pathlib.Path(temp).absolute().exists() else pathlib.Path(temp).absolute().stat().st_size
            if total and _attempt.get(0) + 1==1:await pipe_.coro_send(  (None, 0,total))
            if not total or total>resume_size:
                headers= {"Range":f"bytes={resume_size}-{total}"} if pathlib.Path(temp).exists() else None
                params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
                item["path"]=temp
                async with c.requests(url=url,headers=headers,params=params)() as l:                
                    if l.ok:
                        pathstr=str(temp)
                        item["total"]=total or int(l.headers['content-length'])
                        total=item["total"]
                        data=l.headers
                        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,f"{item['name']}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))
                        check1=check_forced_skip(ele,item["total"])
                        if check1:
                            return check1
                        innerlog.get().debug(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
                        await pipe_.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                                    "total":total,"visible":False})
                        await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":resume_size,"visible":True})     
                        count=0
                        
                        async with aiofiles.open(temp, 'ab') as f:                                              
                            async for chunk in l.iter_chunked(constants.maxChunkSizeB):
                                count=count+1
                                innerlog.get().trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
                                await f.write(chunk)
                                if count==constants.CHUNK_ITER:await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":(pathlib.Path(temp).absolute().stat().st_size)});count=0
                        await pipe_.coro_send({"type":"remove_task","args":(ele.id,)})

                    else:
                        innerlog.get().debug(f"[bold]  {get_medialog(ele)}  main download data finder status[/bold]: {l.status}")
                        innerlog.get().debug(f"[bold] {get_medialog(ele)}  main download data finder text [/bold]: {await l.text_()}")
                        innerlog.get().debug(f"[bold]  {get_medialog(ele)} main download data finder headeers [/bold]: {l.headers}")   
                        l.raise_for_status()
                size_checker(temp,ele,total) 
                await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.touch,f"{ele.filename}_headers",1))
            return item
                
        except Exception as E:
            innerlog.get().traceback(traceback.format_exc())
            innerlog.get().traceback(E)   
            raise E
        finally:
            await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)

    return await inner(item,c,ele)




@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using cdrm auto key helper")
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} cdrm auto key helper got key from cache")
            return out
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license': licence_url,
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': '',
            'proxy': '',
            'cache': True,
        }
        async with c.requests(url=constants.CDRM,method="post",json=json_data)() as r:
            httpcontent=await r.text_()
            log.debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, 'html.parser')
            out=soup.find("li").contents[0]
            await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
          
        return out
    except Exception as E:
        log.traceback(E)
        log.traceback(traceback.format_exc())
        raise E 
    finally:
        await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)

     


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm2(c,pssh,licence_url,id):
    innerlog.get().debug(f"ID:{id} using cdrm auto key helper")
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        innerlog.get().debug(f"ID:{id} pssh: {pssh!=None}")
        innerlog.get().debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            innerlog.get().debug(f"ID:{id} cdrm auto key helper got key from cache")
            return out
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license': licence_url,
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': 'google/sdk_gphone_x86/generic_x86:8.1.0/OSM1.180201.037/6739391:userdebug/dev-keys',
            'proxy': '',
            'cache': True,
        }
        async with c.requests(url=constants.CDRM2,method="post",json=json_data)() as r:
            httpcontent=await r.text_()
            innerlog.get().debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, 'html.parser')
            out=soup.find("li").contents[0]
            await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
        return out
    except Exception as E:
        innerlog.get().traceback(E)
        innerlog.get().traceback(traceback.format_exc())
        raise E
    finally:
        await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_keydb(c,pssh,licence_url,id):
    innerlog.get().debug(f"ID:{id} using keydb auto key helper")
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        innerlog.get().debug(f"ID:{id} pssh: {pssh!=None}")
        innerlog.get().debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            innerlog.get().debug(f"ID:{id} keydb auto key helper got key from cache")
            return out
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license_url': licence_url,
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': '',
            'proxy': '',
            'cache': True,
        }
  
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Ktesttemp, like Gecko) Chrome/90.0.4430.85 Safari/537.36",
            "Content-Type": "application/json",
            "X-API-Key": config_.get_keydb_api(config_.read_config()),
        }
   
        async with c.requests(url=constants.KEYDB,method="post",json=json_data,headers=headers)() as r:            
            data=await r.json()
            innerlog.get().debug(f"keydb json {data}")
            if  isinstance(data,str): out=data
            elif isinstance(data["keys"][0],str):
                out=data["keys"][0]
            elif  isinstance(data["keys"][0],object):
                 out==data["keys"][0]["key"]
            await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))

        return out
    except Exception as E:
        innerlog.get().traceback(E)
        innerlog.get().traceback(traceback.format_exc())
        raise E
    finally:
        await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)

       
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_manual(c,pssh,licence_url,id):
    innerlog.get().debug(f"ID:{id} using manual key helper")
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        if out!=None:
            innerlog.get().debug(f"ID:{id} manual key helper got key from cache")
            return out
        innerlog.get().debug(f"ID:{id} pssh: {pssh!=None}")
        innerlog.get().debug(f"ID:{id} licence: {licence_url}")

        # prepare pssh
        pssh = PSSH(pssh)


        # load device
        private_key=pathlib.Path(config_.get_private_key(config_.read_config())).read_bytes()
        client_id=pathlib.Path(config_.get_client_id(config_.read_config())).read_bytes()
        device = Device(security_level=3,private_key=private_key,client_id=client_id,type_="ANDROID",flags=None)


        # load cdm
        cdm = Cdm.from_device(device)

        # open cdm session
        session_id = cdm.open()

        
        keys=None
        challenge = cdm.get_license_challenge(session_id, pssh)
        async with c.requests(url=licence_url,method="post",data=challenge)() as r:
            cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
            cdm.parse_license(session_id, (await r.content.read()))
            keys = cdm.get_keys(session_id)
            cdm.close(session_id)
        keyobject=list(filter(lambda x:x.type=="CONTENT",keys))[0]
        key="{}:{}".format(keyobject.kid.hex,keyobject.key.hex())
        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
        return key
    except Exception as E:
        innerlog.get().traceback(E)
        innerlog.get().traceback(traceback.format_exc())
        raise E 
    finally:
        await asyncio.get_event_loop().run_in_executor(cache_thread,cache.close)
  
                

    


def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
      return '0 B'
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f'{round(num_bytes / 10**9, 2)} GB'
    return f'{round(num_bytes / 10 ** 6, 2)} MB'

               
def set_time(path, timestamp):
    if platform.system() == 'Windows':
        setctime(path, timestamp)
    pathlib.os.utime(path, (timestamp, timestamp))


def get_error_message(content):
    error_content = content.get('error', 'No error message available')
    try:
        return error_content.get('message', 'No error message available')
    except AttributeError:
        return error_content


def set_cache_helper(ele):
    cache = Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))

    if  ele.postid and ele.responsetype_=="profile":
        cache.set(ele.postid ,True)
        cache.close()


def addLocalDir(path):
    localdirSet.add(path.resolve().parent)
def addGlobalDir(newSet):
    global dirSet
    global dir_lock
    with dir_lock:
        dirSet.update(newSet)
def setDirectoriesDate():
    global dirSet
    log=logging.getLogger("shared")
    log.info( f" {pid_log_helper()} Setting Date for modified directories")
    output=set()
    rootDir=pathlib.Path(config_.get_save_location(config_.read_config())).resolve()
    for ele in dirSet:
        output.add(ele)
        while ele!=rootDir and ele.parent!=rootDir:
            log.debug(f"{pid_log_helper()} Setting Dates ele:{ele} rootDir:{rootDir}")
            output.add(ele.parent)
            ele=ele.parent
    log.debug(f"{pid_log_helper()} Directories list {rootDir}")
    for ele in output:
        try:
            set_time(ele,dates.get_current_time())
        except PermissionError as E:
            log.traceback(E)
            log.traceback(traceback.format_exc())
