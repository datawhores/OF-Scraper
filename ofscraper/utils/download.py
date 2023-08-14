r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import sys
from collections import abc
import asyncio
import math
import pathlib
import platform
import shutil
import traceback
import re
import logging
import contextvars
import json
import subprocess
from functools import singledispatch,partial
from rich.progress import Progress
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
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type

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
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.classes.placeholder as placeholder
import ofscraper.classes.sessionbuilder as sessionbuilder



from diskcache import Cache
attempt = contextvars.ContextVar("attempt")
attempt2 = contextvars.ContextVar("attempt")
total_count = contextvars.ContextVar("total")
total_count2 = contextvars.ContextVar("total")

mpd_sem = semaphoreDelayed(config_.get_download_semaphores(config_.read_config()))
total_sem = semaphoreDelayed(config_.get_download_semaphores(config_.read_config()))
sem = semaphoreDelayed(config_.get_download_semaphores(config_.read_config()))



def get_medialog(ele):
    return f"Media:{ele.id} Post:{ele.postid}"



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





async def update_total(update):
    global total_data
    global lock
    async with lock:
        total_data+=update
        



async def process_dicts(username, model_id, medialist):
    with stdout.lowstdout():
        overall_progress=Progress(  TextColumn("{task.description}"),
        BarColumn(),TaskProgressColumn(),TimeElapsedColumn())
        job_progress=Progress(TextColumn("{task.description}",table_column=Column(ratio=2)),BarColumn(), \
        TaskProgressColumn(),TimeRemainingColumn(),TransferSpeedColumn(),DownloadColumn(),disable=(config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars)==False)
        
        progress_group = Group(
        overall_progress
        , Panel(Group(job_progress,fit=True)))
        # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8
      


        global dirSet
        dirSet=set()
        global file_size_limit
        file_size_limit = args_.getargs().size_max or config_.get_filesize_limit(config_.read_config()) 
        global file_size_min
        file_size_min=args_.getargs().size_min or config_.get_filesize_limit(config_.read_config()) 
      
        global log
        log=logging.getLogger(__package__)
        #log directly to stdout
        log.addHandler(logger.QueueHandler(logger.otherqueue_))
        global log_trace
        log_trace=True if "TRACE" in set([args_.getargs().log,args_.getargs().output,args_.getargs().discord]) else False

        global maxfile_sem
        maxfile_sem = semaphoreDelayed(config_.get_maxfile_semaphores(config_.read_config()))
        global total_data
        total_data=0
        global lock
        lock=asyncio.Lock()

     

        
        with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.shared_console):               
                aws=[]
                photo_count = 0
                video_count = 0
                audio_count=0
                skipped = 0
                forced_skipped=0
                total_downloaded = 0
                desc = 'Progress: ({p_count} photos, {v_count} videos, {a_count} audios, {forced_skipped} skipped, {skipped} failed || {sumcount}/{mediacount}||{total_bytes_download}/{total_bytes})'    

                async with sessionbuilder.sessionBuilder() as c:
                    for ele in medialist:
                        aws.append(asyncio.create_task(download(c,ele ,model_id, username,job_progress)))
                    task1 = overall_progress.add_task(desc.format(p_count=photo_count, v_count=video_count,a_count=audio_count, skipped=skipped,mediacount=len(medialist),forced_skipped=forced_skipped, sumcount=0,total_bytes_download=0,total_bytes=0), total=len(aws),visible=True)
                    progress_group.renderables[1].height=max(15,console.shared_console.size[1]-2)
                    for coro in asyncio.as_completed(aws):
                            try:
                                media_type, num_bytes_downloaded = await coro
                            except Exception as e:
                                log.traceback(e)
                                log.traceback(traceback.format_exc())
                                media_type = "skipped"
                                num_bytes_downloaded = 0

                            total_downloaded += num_bytes_downloaded
                            total_bytes_downloaded=convert_num_bytes(total_downloaded)
                            total_bytes=convert_num_bytes(total_data)
                            if media_type == 'images':
                                photo_count += 1 

                            elif media_type == 'videos':
                                video_count += 1
                            elif media_type == 'audios':
                                audio_count += 1
                            elif media_type == 'skipped':
                                skipped += 1
                            elif media_type== 'forced_skipped':
                                 forced_skipped+=1
                            overall_progress.update(task1,description=desc.format(
                                        p_count=photo_count, v_count=video_count, a_count=audio_count,skipped=skipped, forced_skipped=forced_skipped,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped+forced_skipped,total_bytes=total_bytes,total_bytes_download=total_bytes_downloaded), refresh=True, advance=1)
        overall_progress.remove_task(task1)
    setDirectoriesDate()
    log.error(f'[bold]{username}[/bold] ({photo_count} photos, {video_count} videos, {audio_count} audios,  {skipped} skipped)' )
    return photo_count+video_count+audio_count,skipped
def retry_required(value):
    return value == ('skipped', 1)

async def download(c,ele,model_id,username,progress):

    async with maxfile_sem:
        try:
                with paths.set_directory(placeholder.Placeholders().getmediadir(ele,username,model_id)):
                    if ele.url:
                        return await main_download_helper(c,ele,pathlib.Path(".").absolute(),username,model_id,progress)
                    elif ele.mpd:
                        return await alt_download_helper(c,ele,pathlib.Path(".").absolute(),username,model_id,progress)
                    else:
                        return None
        except Exception as e:
            log.debug(f"exception {e}")   
            log.debug(f"exception {traceback.format_exc()}")   
            return 'skipped', 1
async def main_download_helper(c,ele,path,username,model_id,progress):
    path_to_file=None

    log.debug(f"{get_medialog(ele)} Downloading with normal downloader")
    #total may be none if no .part file
    data=await main_download_data(c,path,ele)
    total ,temp,path_to_file=await main_download_downloader(c,ele,path,username,model_id,progress,data)
    if temp=="forced_skipped":
        return "forced_skipped",0
    elif total==0:
        return ele.mediatype,total
    elif not pathlib.Path(temp).exists():
        log.debug(f"{get_medialog(ele)} {temp} was not created") 
        return "skipped",1
    elif abs(total-pathlib.Path(temp).absolute().stat().st_size)>500:
        log.debug(f"{get_medialog(ele)} size mixmatch target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        return "skipped",1 
    else:
        log.debug(f"{get_medialog(ele)} {ele.filename_} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        log.debug(f"{get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}")   
        shutil.move(temp,path_to_file)
        addGlobalDir(path)
        if ele.postdate:
            newDate=dates.convert_local_time(ele.postdate)
            log.debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
            set_time(path_to_file,newDate )
            log.debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  

        if ele.id:
            await operations.write_media_table(ele,path_to_file,model_id,username)
        set_cache_helper(ele)
        return ele.mediatype,total

async def main_download_data(c,path,ele):
    temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
    total_count.set(attempt.get(0) + 1) 
    pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None
    if not paths.truncate(temp).exists():
        return None
    @retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
    @sem_wrapper(total_sem)
    async def inner(c,ele):
        try:    
            url=ele.url
            log.debug(f"{get_medialog(ele)} [attempt {total_count.get()}/{constants.NUM_TRIES}] Getting size of  media {ele.filename_} with {url}")
            async with c.requests(url=url)() as r:
                    if r.ok:
                        rheaders=r.headers
                        return rheaders
                    else:
                        r.raise_for_status()   
        except Exception:
            raise Exception 
    return await inner(c,ele)






async def main_download_downloader(c,ele,path,username,model_id,progress,data):  
    if data and data.get('Content-Length'):
            temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
            content_type = data.get("content-type").split('/')[-1]
            total=data.get('Content-Length')
            filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
            path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
            resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
            if total==0:
                log.debug(f"{get_medialog(ele)} not downloading because content length was zero")                  
                return total ,temp,path_to_file      
            elif file_size_limit>0 and total > int(file_size_limit): 
                return 0,"forced_skipped",1  
            elif file_size_min>0 and total < int(file_size_min): 
                return 0,"forced_skipped",1
            if total<resume_size:
                return total ,temp,path_to_file

    @retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
    @sem_wrapper
    async def inner(c,ele,path,username,model_id,progress,total):  
        attempt.set(attempt.get(0) + 1) 
        try: 
            temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
            log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
            resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
            url=ele.url
            headers=None if total==None else {"Range":f"bytes={resume_size}-{total}"}
            async with c.requests(url=url,headers=headers)() as r:
                    if r.ok:
                        data=r.headers
                        total=int(data['Content-Length'])
                        if attempt.get()==1:await update_total(total)
                        content_type = data.get("content-type").split('/')[-1]
                        if not content_type and ele.mediatype.lower()=="videos":content_type="mp4"
                        if not content_type and ele.mediatype.lower()=="images":content_type="jpg"
                        temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
                        filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                        log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] filename from config {filename}")
                        log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] full path from config {pathlib.Path(path,f'{filename}')}")
                        path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
                        log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] full path trunicated from config {path_to_file}")
                        log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] passed size check with size {total}")   
                        pathstr=str(path_to_file)
                        if total==0:
                            log.debug(f"{get_medialog(ele)} not downloading because content length was zero")                  
                            return total ,temp,path_to_file      
                        elif file_size_limit>0 and total > int(file_size_limit): 
                            return 0,"forced_skipped",1  
                        elif file_size_min>0 and total < int(file_size_min): 
                            return 0,"forced_skipped",1
                        log.debug(f"{get_medialog(ele)} passed size check with size {total}")    
                        pathstr=str(path_to_file)
                        task1 = progress.add_task(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n", total=total,visible=True)
                        count=0
                        with open(temp, 'ab') as f: 
                            async for chunk in r.iter_chunked(constants.maxChunkSize):
                                count=count+1
                                log.trace(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}]  Download:{len(chunk)}/{(pathlib.Path(temp).absolute().stat().st_size)}")
                                f.write(chunk)
                                if count==constants.CHUNK_ITER:progress.update(task1, completed=(pathlib.Path(temp).absolute().stat().st_size));count=0
                            progress.remove_task(task1)  
                    else:
                        r.raise_for_status()               
            return total ,temp,path_to_file
        except Exception as E:
            log.traceback(traceback.format_exc())
            log.traceback(E)
            raise E
    total=(data or {}).get('Content-Length')
    return await inner(c,ele,path,username,model_id,progress,total)
    
async def alt_download_helper(c,ele,path,username,model_id,progress):
    log.debug(f"{get_medialog(ele)} Downloading with protected media downloader")      
    filename=f'{placeholder.Placeholders().createfilename(ele,username,model_id,"mp4")}'
    log.debug(f"{get_medialog(ele)} filename from config {filename}")
    log.debug(f"{get_medialog(ele)} full filepath from config{pathlib.Path(path,filename)}")
    path_to_file = paths.truncate(pathlib.Path(path,filename))
    log.debug(f"{get_medialog(ele)} full path trunicated from config {path_to_file}")
    temp_path=paths.truncate(pathlib.Path(path,f"temp_{ele.id or ele.filename_}.mp4"))
    log.debug(f"{get_medialog(ele)}  temporary path from combined audio/video {temp_path}")
    audio,video=await alt_download_preparer(ele)
    audio=await alt_download_get_total(audio,c,ele,path)
    video=await alt_download_get_total(video,c,ele,path)   

    audio=await alt_download_downloader(audio,c,ele,path,progress)
    video=await alt_download_downloader(video,c,ele,path,progress) 
    if audio["total"]==0 and video["total"]==0:
        return ele.mediatype,audio["total"]+video["total"]
    elif int(file_size_limit)>0 and int(video["total"] or 0)+int(audio["total"] or 0) > int(file_size_limit): 
            log.debug(f"{get_medialog(ele)} over size limit") 
            return 'forced_skipped', 0
    elif int(file_size_min)>0 and int(video["total"])+int(audio["total"]  or sys.maxsize) < int(file_size_min): 
            log.debug(f"{get_medialog(ele)} under size min") 
            return 'forced_skipped', 0
    elif int(video["total"])==0 or int(audio["total"])==0:
            log.debug("skipping because content length was zero") 
            return ele.mediatype,audio["total"]+video["total"]
    
    for item in [audio,video]:
        log.debug(f"temporary file name for protected media {item['path']}")
        if not pathlib.Path(item["path"]).exists():
                log.debug(f"{get_medialog(ele)} {item['path']} was not created") 
                return "skipped",1
        elif abs(item["total"]-pathlib.Path(item['path']).absolute().stat().st_size)>500:
            log.debug(f"{get_medialog(ele)} {item['name']} size mixmatch target: {item['total']} vs actual: {pathlib.Path(item['path']).absolute().stat().st_size}")   
            return "skipped",1             
    for item in [audio,video]:
        key=None
        keymode=(args_.getargs().key_mode or config_.get_key_mode(config_.read_config()) or "cdrm")
        if  keymode== "manual": key=await key_helper_manual(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="keydb":key=await key_helper_keydb(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="cdrm": key=await key_helper_cdrm(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="cdrm2": key=await key_helper_cdrm2(c,item["pssh"],ele.license,ele.id) 
        if key==None:
            log.debug(f"{get_medialog(ele)} Could not get key")
            return "skipped",1 
        log.debug(f"{get_medialog(ele)} got key")
        newpath=pathlib.Path(re.sub("\.part$","",str(item["path"]),re.IGNORECASE))
        log.debug(f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}")   
        r=subprocess.run([config_.get_mp4decrypt(config_.read_config()),"--key",key,str(item["path"]),str(newpath)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if not pathlib.Path(newpath).exists():
            log.debug(f"{get_medialog(ele)} mp4decrypt failed")
            log.debug(f"{get_medialog(ele)} mp4decrypt {r.stderr.decode()}")
            log.debug(f"{get_medialog(ele)} mp4decrypt {r.stdout.decode()}")
        else:
            log.debug(f"{get_medialog(ele)} mp4decrypt success {newpath}")    
        pathlib.Path(item["path"]).unlink(missing_ok=True)
        item["path"]=newpath
    
    path_to_file.unlink(missing_ok=True)
    temp_path.unlink(missing_ok=True)
    t=subprocess.run([config_.get_ffmpeg(config_.read_config()),"-i",str(video["path"]),"-i",str(audio["path"]),"-c","copy","-movflags", "use_metadata_tags",str(temp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if t.stderr.decode().find("Output")==-1:
        log.debug(f"{get_medialog(ele)} ffmpeg failed")
        log.debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        log.debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")

    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    log.debug(f"Moving intermediate path {temp_path} to {path_to_file}")
    shutil.move(temp_path,path_to_file)
    addGlobalDir(path_to_file)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        log.debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        log.debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.write_media_table(ele,path_to_file,model_id,username)
    return ele.mediatype,audio["total"]+video["total"]


@sem_wrapper(mpd_sem)
async def alt_download_preparer(ele):
    log.debug(f"{get_medialog(ele)} Attempting to get info for {ele.filename_} with {ele.mpd}")
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

async def alt_download_downloader(item,c,ele,path,progress):
    base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
    url=f"{base_url}{item['origname']}"
    log.debug(f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}")
    params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
    temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
    item["path"]=temp
    if item["total"]==0:
        return item
    @retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
    @sem_wrapper    
    async def inner(item,c,ele,progress):
        if ele["type"]=="video":_attempt=attempt
        if ele["type"]=="audio":_attempt=attempt2
        _attempt.set(_attempt.get(0) + 1) 
        try:
            pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None
            resume_size=0 if not pathlib.Path(temp).absolute().exists() else pathlib.Path(temp).absolute().stat().st_size
            total=item["total"]
            if total>resume_size:
                if _attempt.get(0) + 1==1:await update_total(total)
                headers= {"Range":f"bytes={resume_size}-{total}"} if total else None
                async with c.requests(url=url,headers=headers,params=params)() as l:                
                    if l.ok:
                        pathstr=str(temp)
                        item["total"]=total or int(l.headers['Content-Length'])
                        total=item["total"]
                        if total==0:
                            return item   
                        log.debug(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
                        task1 = progress.add_task(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n", total=total,visible=True)
                        progress.update(task1, advance=resume_size)
                        with open(temp, 'ab') as f:                           
                            size=0
                            count=0
                            async for chunk in l.iter_chunked(constants.maxChunkSize):
                                size=size+len(chunk)
                                count=count+1
                                log.trace(f"{get_medialog(ele)} Download:{len(chunk)}/{(pathlib.Path(temp).absolute().stat().st_size)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] ")
                                f.write(chunk)
                                if count==constants.CHUNK_ITER:progress.update(task1, completed=(pathlib.Path(temp).absolute().stat().st_size));count=0
                            progress.remove_task(task1)
                    else:
                        l.raise_for_status()
                        return item
            return item
                
        except Exception as E:
            log.traceback(traceback.format_exc())
            log.traceback(E)
            raise E
    return await inner(item,c,ele,progress)
   


async def alt_download_get_total(item,c,ele,path):
    temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
    pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None
    if not paths.truncate(temp).exists() and file_size_limit==0 and file_size_min==0:
        item["total"]=None
        return item
    @retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
    @sem_wrapper(total_sem)
    async def inner(item,c,ele):
        if item["type"]=="video":_total_count=total_count
        if item["type"]=="audio":_total_count=total_count2
        _total_count.set(_total_count.get(0) + 1)  

        try:
            base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
            url=f"{base_url}{item['origname']}"
            log.debug(f"{get_medialog(ele)} [attempt {_total_count.get()}/{constants.NUM_TRIES}] Getting size of  media {ele.filename_} with {url}")
            params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
            total=None

            async with c.requests(url=url,params=params)() as r:
                if r.ok:
                    rheaders=r.headers
                    total = int(rheaders['Content-Length'])
                else:
                    r.raise_for_status()  
            item["total"]=total
            return item
                
        except Exception as E:
            log.traceback(traceback.format_exc())
            log.traceback(E)
            raise E
    return await inner(item,c,ele)
  

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using auto key helper")
    cache = Cache(paths.getcachepath())
    try:
        out=cache.get(licence_url)
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} auto key helper got key from cache")
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
async def key_helper_cdrm(c,pssh,licence_url,id):
    cache = Cache(paths.getcachepath())
    log.debug(f"ID:{id} using cdrm auto key helper")
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
    cache = Cache(paths.getcachepath())
    log.debug(f"ID:{id} using cdrm2 auto key helper")
    try:
        out=cache.get(licence_url)
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} cdrm2 auto key helper got key from cache")
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
async def key_helper_keydb(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using keydb auto key helper")
    cache = Cache(paths.getcachepath())
    try:
        out=cache.get(licence_url)
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} keydb auto key helper got key from cache")
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
            log.debug(f"keydb json {data}")
            if  isinstance(data,str): out=data
            elif  isinstance(data,object): out=data["keys"][0]["key"]
            cache.set(licence_url,out, expire=constants.KEY_EXPIRY)
            cache.close()
        return out
    except Exception as E:
        log.traceback(E)
        log.traceback(traceback.format_exc())
        raise E  

async def key_helper_manual(c,pssh,licence_url,id):
    cache = Cache(paths.getcachepath())
    log.debug(f"ID:{id} using manual key helper")
    out=cache.get(licence_url)
    if out!=None:
        log.debug(f"ID:{id} manual key helper got key from cache")
        return out
    log.debug(f"ID:{id} pssh: {pssh!=None}")
    log.debug(f"ID:{id} licence: {licence_url}")

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
        cdm.parse_license(session_id, (await r.content.read()))
        keys = cdm.get_keys(session_id)
        cdm.close(session_id)
    keyobject=list(filter(lambda x:x.type=="CONTENT",keys))[0]
    key="{}:{}".format(keyobject.kid.hex,keyobject.key.hex())
    cache.set(licence_url,key, expire=constants.KEY_EXPIRY)
    return key

                

    


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


def addGlobalDir(path):
    dirSet.add(path.parent)


def setDirectoriesDate():
    log.info("Setting Date for modified directories")
    output=set()
    rootDir=pathlib.Path(config_.get_save_location(config_.read_config()))
    for ele in dirSet:
        output.add(ele)
        while ele!=rootDir and ele.parent!=rootDir:
            log.debug(f"Setting Dates ele:{ele} rootDir:{rootDir}")
            output.add(ele.parent)
            ele=ele.parent
    log.debug(f"Directories list {rootDir}")
    for ele in output:
        set_time(ele,dates.get_current_time())