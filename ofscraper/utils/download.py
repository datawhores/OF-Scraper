r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import math
import os
import pathlib
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
import ofscraper.utils.separate as seperate
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
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import ofscraper.classes.placeholder as placeholder
import ofscraper.classes.sessionbuilder as sessionbuilder
from   ofscraper.classes.multiprocessprogress import MultiprocessProgress as progress 
import ofscraper.utils.misc as misc
from aioprocessing import AioPipe
if platform.system() == 'Windows':
    from win32_setctime import setctime 
 # pylint: disable=import-errorm
 
#main thread queues
logqueue_=logger.queue_

def reset_globals():
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

#start other thread here
def process_dicts(username,model_id,medialist):
    #reset globals
    reset_globals()
    log=logging.getLogger("shared")
    random.shuffle(medialist)
    if len(medialist)==0:
        log.error("Media list empty")
        return
    mediasplits=get_mediasplits(medialist)
    num_proc=len(mediasplits)
    split_val=min(4,num_proc)
    log.debug(f"Number of process {num_proc}")
    connect_tuples=[AioPipe() for i in range(num_proc)]

    shared=list(more_itertools.chunked([i for i in range(num_proc)],split_val))
    #ran by main process cause of stdout
    logqueues_=[aioprocessing.AioQueue()  for i in range(len(shared))]
    #ran by other ofscraper_
    otherqueues_=[aioprocessing.AioQueue()  for i in range(len(shared))]
    
    #start main queue consumers
    logthreads=[logger.start_stdout_logthread(input_=logqueues_[i],name=f"ofscraper_{model_id}_{i+1}",count=len(list(shared[i]))) for i in range(len(shared))]
    #start producers
    stdout_logs=[logger.get_shared_logger(main_=logqueues_[i//split_val],other_=otherqueues_[i//split_val],name=f"shared_{model_id}_{i+1}") for i in range(num_proc) ]
    #For some reason windows loses queue when not passed seperatly
    processes=[ aioprocessing.AioProcess(target=process_dict_starter, args=(username,model_id,mediasplits[i],stdout_logs[i].handlers[0].queue,stdout_logs[i].handlers[1].queue,connect_tuples[i][1])) for i in range(num_proc)]
    try:
        [process.start() for process in processes]      
        downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars
        job_progress=progress(TextColumn("{task.description}",table_column=Column(ratio=2)),BarColumn(),
            TaskProgressColumn(),TimeRemainingColumn(),TransferSpeedColumn(),DownloadColumn())      
        overall_progress=Progress(  TextColumn("{task.description}"),
        BarColumn(),TaskProgressColumn(),TimeElapsedColumn())
        progress_group = Group(overall_progress,Panel(Group(job_progress,fit=True)))
        task1 = overall_progress.add_task(desc.format(p_count=photo_count, v_count=video_count,a_count=audio_count, skipped=skipped,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped,forced_skipped=forced_skipped,data=data,total=total_data), total=len(medialist),visible=True)
        progress_group.renderables[1].height=max(15,console.get_shared_console().size[1]-2) if downloadprogress else 0
        with stdout.lowstdout():
            with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.get_shared_console()):
                queue_threads=[threading.Thread(target=queue_process,args=(connect_tuples[i][0],overall_progress,job_progress,task1,len(medialist)),daemon=True) for i in range(num_proc)]
                [thread.start() for thread in queue_threads]
                while len(list(filter(lambda x:x.is_alive(),queue_threads)))>0: 
                    for thread in queue_threads:
                        thread.join(1)
                        time.sleep(5)
        [logthread.join() for logthread in logthreads]
        [process.join(timeout=1) for process in processes]    
        [process.terminate() for process in processes]
        overall_progress.remove_task(task1)
        progress_group.renderables[1].height=0
        setDirectoriesDate()    
        log.error(f'[bold]{username}[/bold] ({photo_count} photos, {video_count} videos, {audio_count} audios, {forced_skipped} skipped, {skipped} failed)' )
        return photo_count,video_count,audio_count,forced_skipped,skipped
    except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    [process.terminate() for process in processes]  
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                    raise KeyboardInterrupt
    except Exception as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    [process.terminate() for process in processes]  
                    raise E
            except KeyboardInterrupt:
               
                  raise KeyboardInterrupt  
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
    final_count=min(user_count,misc.getcpu_count(), len(medialist)//5)
    if final_count==0:final_count=1
    return more_itertools.divide(final_count, medialist   )
def process_dict_starter(username,model_id,ele,p_logqueue_,p_otherqueue_,pipe_):
    log=logger.get_shared_logger(main_=p_logqueue_,other_=p_otherqueue_,name=f"shared_{os.getpid()}")
    asyncio.run(process_dicts_split(username,model_id,ele,log,p_logqueue_,pipe_))

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

async def process_dicts_split(username, model_id, medialist,logCopy,logqueueCopy,pipecopy):
    global innerlog
    innerlog = contextvars.ContextVar("innerlog")
    global log 
    log=logCopy
    logCopy.debug(f"{pid_log_helper()} start inner thread for other loggers")   
    global logqueue_
    logqueue_=logqueueCopy
    #start consumer for other
    other_thread=logger.start_other_thread(input_=logCopy.handlers[1].queue,name=str(os.getpid()),count=1)
    setpriority()
    global attempt
    attempt=contextvars.ContextVar("attempt")
    

 
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

    
    

    if not args_.getargs().dupe:
        media_ids = set(operations.get_media_ids(model_id,username))
        split_log.debug(f"{pid_log_helper()} number of unique media ids in database for {username}: {len(media_ids)}")
        medialist = seperate.separate_by_id(medialist, media_ids)
        split_log.debug(f"{pid_log_helper()} Number of new mediaids with dupe ids removed: {len(medialist)}")  
        medialist=seperate.seperate_avatars(medialist)
        split_log.debug(f"{pid_log_helper()} Remove avatar")
        split_log.debug(f"{pid_log_helper()} Final Number of media to download {len(medialist)}")

    else:
        split_log.info(f"{pid_log_helper()} forcing all downloads media count {len(medialist)}")
    global file_size_limit
    global file_size_min
    file_size_limit = args_.getargs().size_max or config_.get_filesize_limit(config_.read_config()) 
    file_size_min = args_.getargs().size_min or config_.get_filesize_min(config_.read_config()) 
        
    aws=[]

    async with sessionbuilder.sessionBuilder() as c:
        i=0
        for ele in medialist:
            aws.append(asyncio.create_task(download(c,ele ,model_id, username)))

        for coro in asyncio.as_completed(aws):
                try:
                    media_type, num_bytes_downloaded = await coro
                    await pipe_.coro_send(  (media_type, num_bytes_downloaded,0))
                except Exception as e:
                    split_log.traceback(e)
                    split_log.traceback(traceback.format_exc())
                    media_type = "skipped"
                    num_bytes_downloaded = 0
                    await pipe_.coro_send(  (media_type, num_bytes_downloaded,0))
            
    split_log.debug(f"{pid_log_helper()} download process thread closing")
    split_log.critical(None)
    await pipe_.coro_send(localdirSet)
    await pipe_.coro_send(None)
    other_thread.join()
 

def retry_required(value):
    return value == ('skipped', 1)

def pid_log_helper():
    return f"PID: {os.getpid()}"  




async def download(c,ele,model_id,username):
    # reduce number of logs
    async with maxfile_sem:
        templog_=logger.get_shared_logger(name=str(ele.id),main_=aioprocessing.Queue(),other_=aioprocessing.Queue())
        innerlog.set(templog_)

        attempt.set(attempt.get(0) + 1)  
        try:
                with paths.set_directory(placeholder.Placeholders().getmediadir(ele,username,model_id)):
                    if ele.url:
                        return await main_download_helper(c,ele,pathlib.Path(".").absolute(),username,model_id)
                    elif ele.mpd:
                        return await alt_download_helper(c,ele,pathlib.Path(".").absolute(),username,model_id)
        except Exception as e:
            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] exception {e}")   
            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] exception {traceback.format_exc()}")   
            return 'skipped', 1
        finally:
            #dump logs
            await logqueue_.coro_put(list(innerlog.get().handlers[0].queue.queue))
            # we can put into seperate otherqueue_
            await log.handlers[1].queue.coro_put(list(innerlog.get().handlers[1].queue.queue))
async def main_download_helper(c,ele,path,username,model_id): 
    path_to_file=None
    innerlog.get().debug(f"{get_medialog(ele)} Downloading with normal downloader")
    total ,temp,path_to_file=await main_download_downloader(c,ele,path,username,model_id)
    if temp=="forced_skipped":
        return 'forced_skipped',0
    elif total==0:
        return ele.mediatype,total
    elif not pathlib.Path(temp).exists():
        innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {temp} was not created") 
        return "skipped",0
     
    elif abs(total-pathlib.Path(temp).absolute().stat().st_size)>500:
        innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {ele.filename_} size mixmatch target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        return "skipped",0 
    else:
        innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {ele.filename_} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] renaming {pathlib.Path(temp).absolute()} -> {path_to_file}")   
        #move temp file
        if not path_to_file.exists():
            shutil.move(temp,path_to_file)
        elif pathlib.Path(temp).absolute().stat().st_size>=pathlib.Path(path_to_file).absolute().stat().st_size: 
            shutil.move(temp,path_to_file)
        addLocalDir(path)
        if ele.postdate:
            newDate=dates.convert_local_time(ele.postdate)
            innerlog.get().debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
            set_time(path_to_file,newDate )
            innerlog.get().debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
        if ele.id:
            await operations.write_media_table(ele,path_to_file,model_id,username)
        set_cache_helper(ele)
        return ele.mediatype,total

        



 
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def main_download_downloader(c,ele,path,username,model_id):
    try:
        url=ele.url
        innerlog.get().debug(f"{get_medialog(ele)} Attempting to download media {ele.filename_} with {url}")
        total=None
        headers=None
        path_to_file=None
        temp=None
        async with total_sem:
            async with c.requests(url=url)() as r:
                    if r.ok:
                        rheaders=r.headers
                        total = int(rheaders['Content-Length'])
                        content_type = rheaders.get("content-type").split('/')[-1]
                        if not content_type and ele.mediatype.lower()=="videos":content_type="mp4"
                        if not content_type and ele.mediatype.lower()=="images":content_type="jpg"
                        filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                        innerlog.get().debug(f"{get_medialog(ele)} filename from config {filename}")
                        innerlog.get().debug(f"{get_medialog(ele)} full path from config {pathlib.Path(path,f'{filename}')}")
                        path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
                        innerlog.get().debug(f"{get_medialog(ele)} full path trunicated from config {path_to_file}")
                        if file_size_limit>0 and total > int(file_size_limit): 
                                return 0,"forced_skipped",1  
                        elif file_size_min>0 and total < int(file_size_min): 
                                return 0,"forced_skipped",1  
                        innerlog.get().debug(f"{get_medialog(ele)} passed size check with size {total}")    
                        await pipe_.coro_send(  (None, 0,total))
                    else:
                        r.raise_for_status()  
        if total==0:
            innerlog.get().debug(f"{get_medialog(ele)} not downloading because content length was zero")
            return total,temp,path_to_file
   
            



        temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
        pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False or total==0) else None
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size 
        size=resume_size
        filename=None  
                          
        if total!=resume_size:
            async with sem:
                headers={"Range":f"bytes={resume_size}-{total}"}
                async with c.requests(url=url,headers=headers)() as r:
                    if r.ok:
                        pathstr=str(path_to_file)
                        await pipe_.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                                    "total":total,"visible":False})
                        await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":resume_size})
                        count=0
                        with open(temp, 'ab') as f: 
                            await pipe_.coro_send({"type":"update","args":(ele.id,),"visible":True})             
                            async for chunk in r.iter_chunked(constants.maxChunkSize):
                                count=count+1
                                size=size+len(chunk)
                                innerlog.get().trace(f"{get_medialog(ele)} Download:{size}/{total}")
                                f.write(chunk)
                                if count==constants.CHUNK_ITER:await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":size});count=0
                      

                            await pipe_.coro_send({"type":"remove_task","args":(ele.id,)})
                    else:
                        r.raise_for_status()                   
        return total,temp,path_to_file

    except Exception as E:
        innerlog.get().traceback(traceback.format_exc())
        innerlog.geft().traceback(E)
        raise E


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
    #get total seperatly so we can check before download
    audio=await alt_download_get_total(audio,c,ele)
    video=await alt_download_get_total(video,c,ele)
    if int(file_size_limit)>0 and int(video["total"])+int(audio["total"]) > int(file_size_limit): 
        innerlog.get().debug(f"{get_medialog(ele)} over size limit") 
        return 'forced_skipped', 1 
    elif int(file_size_min)>0 and int(video["total"])+int(audio["total"]) < int(file_size_min): 
        innerlog.get().debug(f"{get_medialog(ele)} under size min") 
        return 'forced_skipped', 1
    elif int(video["total"])==0 or int(audio["total"])==0:
        innerlog.get().debug("skipping because content length was zero") 
        return ele.mediatype,audio["total"]+video["total"] 
    audio=await alt_download_downloader(audio,c,ele,path)
    video=await alt_download_downloader(video,c,ele,path)
    innerlog.get().debug(f"{get_medialog(ele)} passed size check with size {int(video['total']) + int(audio['total'])}")    
    for item in [audio,video]:
        innerlog.get().debug(f"temporary file name for protected media {item['path']}") 
        if not pathlib.Path(item["path"]).exists():
                innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {item['path']} was not created") 
                return "skipped",0
        elif abs(item["total"]-pathlib.Path(item['path']).absolute().stat().st_size)>500:
            innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {item['name']} size mixmatch target: {item['total']} vs actual: {pathlib.Path(item['path']).absolute().stat().st_size}")   
            return "skipped",0 
                
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
        innerlog.get().debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] renaming {pathlib.Path(item['path']).absolute()} -> {newpath}")   
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
        innerlog.get().debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        innerlog.get().debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.write_media_table(ele,path_to_file,model_id,username)
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
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def alt_download_get_total(item,c,ele):
    try:
        base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
        url=f"{base_url}{item['origname']}"
        params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
        total=None
        async with total_sem:
            async with c.requests(url=url,params=params)() as r:
                if r.ok:
                    rheaders=r.headers
                    total = int(rheaders['Content-Length'])
                else:
                    r.raise_for_status()  
        item["total"]=total
        return item
              
    except Exception as E:
        innerlog.get().traceback(traceback.format_exc())
        innerlog.get().traceback(E)
        raise E

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def alt_download_downloader(item,c,ele,path):
    try:
        base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
        url=f"{base_url}{item['origname']}"
        innerlog.get().debug(f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}")
        params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
        temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
        pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
        total=item["total"]
        #send total since it passed test
        await pipe_.coro_send(  (None, 0,total))
        if total!=resume_size:
            headers={"Range":f"bytes={resume_size}-{total}"} 
            async with sem:
                async with c.requests(url=url,headers=headers,params=params)() as l:                
                    if l.ok:
                        pathstr=str(temp)
                        await pipe_.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                                        "total":total,"visible":False})
                        await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":resume_size}) 
                        count=0
                        size=resume_size                  
                        with open(temp, 'ab') as f:                           
                            await pipe_.coro_send({"type":"update","args":(ele.id,),"visible":False})
                            async for chunk in l.iter_chunked(constants.maxChunkSize):
                                count=count+1
                                size=size+len(chunk)
                                innerlog.get().trace(f"{get_medialog(ele)} Download:{size}/{total}")
                                f.write(chunk)
                                if count==constants.CHUNK_ITER:await pipe_.coro_send({"type":"update","args":(ele.id,),"completed":size});count=0
                        await pipe_.coro_send({"type":"remove_task","args":(ele.id,)})
                    else:
                        l.raise_for_status()
        item["path"]=temp
        return item
              
    except Exception as E:
        innerlog.get().traceback(traceback.format_exc())
        innerlog.get().traceback(E)
        raise E

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using cdrm auto key helper")
    cache = Cache(paths.getcachepath())
    try:
        out=cache.get(licence_url)
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
        async with c.requests(url='https://cdrm-project.com/wv',method="post",json=json_data)() as r:
            httpcontent=await r.text_()
            log.debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, 'html.parser')
            out=soup.find("li").contents[0]
            cache.set(licence_url,out, expire=constants.KEY_EXPIRY)
            cache.close()
        return out
    except Exception as E:
        log.traceback(E)
        log.traceback(traceback.format_exc())
        raise E       


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm2(c,pssh,licence_url,id):
    innerlog.get().debug(f"ID:{id} using cdrm auto key helper")
    cache = Cache(paths.getcachepath())
    try:
        out=cache.get(licence_url)
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
        async with c.requests(url='http://172.106.17.134:8080/wv',method="post",json=json_data)() as r:
            httpcontent=await r.text_()
            innerlog.get().debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, 'html.parser')
            out=soup.find("li").contents[0]
            cache.set(licence_url,out, expire=constants.KEY_EXPIRY)
            cache.close()
        return out
    except Exception as E:
        innerlog.get().traceback(E)
        innerlog.get().traceback(traceback.format_exc())
        raise E

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_keydb(c,pssh,licence_url,id):
    innerlog.get().debug(f"ID:{id} using keydb auto key helper")
    cache = Cache(paths.getcachepath())
    try:
        out=out=cache.get(licence_url)
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
   
        async with c.requests(url='https://keysdb.net/api',method="post",json=json_data,headers=headers)() as r:            
            data=await r.json()
            innerlog.get().debug(f"keydb json {data}")
            if  isinstance(data,str): out=data
            elif  isinstance(data,object): out=data["keys"][0]["key"]
            cache.set(licence_url,out, expire=constants.KEY_EXPIRY)
            cache.close()
        return out
    except Exception as E:
        innerlog.get().traceback(E)
        innerlog.get().traceback(traceback.format_exc())
        raise E       
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_manual(c,pssh,licence_url,id):
    innerlog.get().debug(f"ID:{id} using manual key helper")
    cache = Cache(paths.getcachepath())
    try:
        out=cache.get(licence_url)
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
            cache = Cache(paths.getcachepath())
            cdm.parse_license(session_id, (await r.content.read()))
            keys = cdm.get_keys(session_id)
            cdm.close(session_id)
        keyobject=list(filter(lambda x:x.type=="CONTENT",keys))[0]
        key="{}:{}".format(keyobject.kid.hex,keyobject.key.hex())
        cache.set(licence_url,key, expire=constants.KEY_EXPIRY)
        return key
    except Exception as E:
        innerlog.get().traceback(E)
        innerlog.get().traceback(traceback.format_exc())
        raise E   
                

    


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
    cache = Cache(paths.getcachepath())

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
        set_time(ele,dates.get_current_time())
