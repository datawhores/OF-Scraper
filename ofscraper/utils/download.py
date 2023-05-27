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
import pathlib
import platform
import shutil
import traceback
import re
import logging
import httpx
import contextvars
import json
import subprocess
from rich.progress import Progress
from rich.progress import (
    Progress,
    TimeElapsedColumn,
    TotalFileSizeColumn,
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
import arrow
from bs4 import BeautifulSoup
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from tenacity import retry,stop_after_attempt,wait_random,retry_if_result


import ffmpeg
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
from diskcache import Cache

cache = Cache(paths.getcachepath())
attempt = contextvars.ContextVar("attempt")
log=logging.getLogger(__package__)


async def process_dicts(username, model_id, medialist,forced=False):
    with stdout.lowstdout():
        overall_progress=Progress(  TextColumn("{task.description}"),
        BarColumn(),TaskProgressColumn(),TimeElapsedColumn())
        job_progress=Progress(TextColumn("{task.description}",table_column=Column(ratio=2)),BarColumn(),
        TaskProgressColumn(),TimeRemainingColumn(),TransferSpeedColumn(),TotalFileSizeColumn())
        progress_group = Group(
        overall_progress
        , Panel(Group(job_progress,fit=True)))
        with Live(progress_group, refresh_per_second=constants.refreshScreen,console=console.shared_console):    
                if not forced:
                    media_ids = set(operations.get_media_ids(model_id,username))
                    medialist = seperate.separate_by_id(medialist, media_ids)
                    log.info(f"Skipping previously downloaded\nMedia left for download {len(medialist)}")
                else:
                    log.info("forcing all downloads")
                file_size_limit = config_.get_filesize()
                global sem
                sem = asyncio.Semaphore(8)
            
                aws=[]
                photo_count = 0
                video_count = 0
                audio_count=0
                skipped = 0
                total_bytes_downloaded = 0
                data = 0
                desc = 'Progress: ({p_count} photos, {v_count} videos, {a_count} audios,  {skipped} skipped || {sumcount}/{mediacount}||{data})'    
            
                

                
                for ele in medialist:
                    with paths.set_directory(paths.getmediadir(ele,username,model_id)):
                        aws.append(asyncio.create_task(download(ele,pathlib.Path(".").absolute() ,model_id, username,file_size_limit,job_progress)))
                task1 = overall_progress.add_task(desc.format(p_count=photo_count, v_count=video_count,a_count=audio_count, skipped=skipped,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped,data=data), total=len(aws),visible=True)
                # progress_group.renderables[1].height=max(15,console.shared_console.size[1]-2)
                for coro in asyncio.as_completed(aws):
                        try:
                            media_type, num_bytes_downloaded = await coro
                        except Exception as e:
                            log.traceback(e)
                            log.traceback(traceback.format_exc())
                            media_type = "skipped"
                            num_bytes_downloaded = 0

                        total_bytes_downloaded += num_bytes_downloaded
                        data = convert_num_bytes(total_bytes_downloaded)
                        if media_type == 'images':
                            photo_count += 1 

                        elif media_type == 'videos':
                            video_count += 1
                        elif media_type == 'audios':
                            audio_count += 1
                        elif media_type == 'skipped':
                            skipped += 1
                        overall_progress.update(task1,description=desc.format(
                                    p_count=photo_count, v_count=video_count, a_count=audio_count,skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True, advance=1)
        overall_progress.remove_task(task1)
    log.error(f'[bold]{username}[/bold] ({photo_count} photos, {video_count} videos, {audio_count} audios,  {skipped} skipped)' )
def retry_required(value):
    return value == ('skipped', 1)

@retry(retry=retry_if_result(retry_required),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=20, max=40),reraise=True) 
async def download(ele,path,model_id,username,file_size_limit,progress):
    attempt.set(attempt.get(0) + 1)
    
    try:
        if ele.url:
           return await main_download_helper(ele,path,file_size_limit,username,model_id,progress)
        elif ele.mpd:  
            return await alt_download_helper(ele,path,file_size_limit,username,model_id,progress)
        else:
            return "skipped",1
    except Exception as e:
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] exception {e}")   
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] exception {traceback.format_exc()}")   
        return 'skipped', 1
async def main_download_helper(ele,path,file_size_limit,username,model_id,progress):
    url=ele.url
    path_to_file=None
    async with sem:
            log.debug(f"Media:{ele.id} Post:{ele.postid} Attempting to download media {ele.filename} with {url}")
            log.debug(f"Media:{ele.id} Post:{ele.postid} Downloading with normal downloader")

            async with httpx.AsyncClient(http2=True, follow_redirects=True, timeout=None) as c: 
                auth.add_cookies(c)        
                async with c.stream('GET',url) as r:
                    if not r.is_error:
                        rheaders=r.headers
                        total = int(rheaders['Content-Length'])
                        if file_size_limit>0 and total > int(file_size_limit): 
                                return 'skipped', 1       
                        content_type = rheaders.get("content-type").split('/')[-1]
                        filename=createfilename(ele,username,model_id,content_type)
                        path_to_file = paths.trunicate(pathlib.Path(path,f"{filename}"))                 
                        pathstr=str(path_to_file)
                        temp=paths.trunicate(f"{path_to_file}.part")
                        pathlib.Path(temp).unlink(missing_ok=True)
                        task1 = progress.add_task(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n", total=total,visible=True)
                        with open(temp, 'wb') as f:                           
                            num_bytes_downloaded = r.num_bytes_downloaded
                            progress.update(task1,visible=True )
                            async for chunk in r.aiter_bytes(chunk_size=1024):
                                f.write(chunk)
                                progress.update(task1, advance=r.num_bytes_downloaded - num_bytes_downloaded)
                                num_bytes_downloaded = r.num_bytes_downloaded
                            progress.remove_task(task1) 
        
                    else:
                        r.raise_for_status()
    if not pathlib.Path(temp).exists():
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] {temp} was not created") 
        return "skipped",1
    elif abs(total-pathlib.Path(temp).absolute().stat().st_size)>500:
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] {ele.filename} size mixmatch target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        return "skipped",1 
    else:
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] {ele.filename} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] renaming {pathlib.Path(temp).absolute()} -> {path_to_file}")   
        shutil.move(temp,path_to_file)
        if ele.postdate:
            newDate=dates.convert_local_time(ele.postdate)
            log.debug(f"Media:{ele.id} Post:{ele.postid} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
            set_time(path_to_file,newDate )
            log.debug(f"Media:{ele.id} Post:{ele.postid} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  

        if ele.id:
            operations.write_media_table(ele,path_to_file,model_id,username)
        return ele.mediatype,total

async def alt_download_helper(ele,path,file_size_limit,username,model_id,progress):
    async with sem:
        log.debug(f"Media:{ele.id} Post:{ele.postid} Downloading with protected media downloader")      
        log.debug(f"Media:{ele.id} Post:{ele.postid} Attempting to download media {ele.filename} with {ele.mpd}")
        video = None
        audio = None
        base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
        mpd=ele.parse_mpd
        path_to_file = paths.trunicate(pathlib.Path(path,f'{createfilename(ele,username,model_id,"mp4")}')) 

        for period in mpd.periods:
            for adapt_set in filter(lambda x:x.mime_type=="video/mp4",period.adaptation_sets):             
                kId=None
                for prot in adapt_set.content_protections:
                    if prot.value==None:
                        kId = prot.pssh[0].pssh 
                        break
                maxquality=max(map(lambda x:x.height,adapt_set.representations))
                for repr in adapt_set.representations:
                    if repr.height==maxquality:
                        video={"name":repr.base_urls[0].base_url_value,"pssh":kId,"type":"video"}
                        break
            for adapt_set in filter(lambda x:x.mime_type=="audio/mp4",period.adaptation_sets):             
                kId=None
                for prot in adapt_set.content_protections:
                    if prot.value==None:
                        kId = prot.pssh[0].pssh 
                        logger.updateSenstiveDict(kId,"pssh_code")
                        break
                for repr in adapt_set.representations:
                    audio={"name":repr.base_urls[0].base_url_value,"pssh":kId,"type":"audio"}
                    break
            for item in [audio,video]:
                url=f"{base_url}{item['name']}"
                log.debug(f"Media:{ele.id} Post:{ele.postid} Attempting to download media {item['name']} with {url}")
                params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
                async with httpx.AsyncClient(http2=True, headers = auth.make_headers(auth.read_auth()), follow_redirects=True, timeout=None,params=params) as c: 
                    auth.add_cookies(c) 
                    async with c.stream('GET',url) as r:
                        if not r.is_error:
                            rheaders=r.headers
                            total = int(rheaders['Content-Length'])
                            item["total"]=total
                            if file_size_limit>0 and total > int(file_size_limit): 
                                    return 'skipped', 1       
                            temp= paths.trunicate(pathlib.Path(path,f"{item['name']}.part"))
                            temp.unlink(missing_ok=True)
                            item["path"]=temp
                            pathstr=str(temp)
                            task1 = progress.add_task(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n", total=total,visible=True)
                            with open(temp, 'wb') as f:                           
                                num_bytes_downloaded = r.num_bytes_downloaded
                                progress.update(task1,visible=True )
                                async for chunk in r.aiter_bytes(chunk_size=1024):
                                    f.write(chunk)
                                    progress.update(task1, advance=r.num_bytes_downloaded - num_bytes_downloaded)
                                    num_bytes_downloaded = r.num_bytes_downloaded
                                progress.remove_task(task1) 
                        else:
                            r.raise_for_status()
    log.debug(f"Media:{ele.id} Post:{ele.postid} video name:{video['name']}")
    log.debug(f"Media:{ele.id} Post:{ele.postid} audio name:{audio['name']}")
    for item in [audio,video]:
        if not pathlib.Path(item["path"]).exists():
                log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] {item['path']} was not created") 
                return "skipped",1
        elif abs(item["total"]-pathlib.Path(item['path']).absolute().stat().st_size)>500:
            log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] {item['name']} size mixmatch target: {total} vs actual: {pathlib.Path(item['path']).absolute().stat().st_size}")   
            return "skipped",1 
                
    for item in [audio,video]:
        key=await key_helper(item["pssh"],ele.license,ele.id)
        if key==None:
            log.debug(f"Media:{ele.id} Post:{ele.postid} Could not get key")
            return "skipped",1 
        log.debug(f"Media:{ele.id} Post:{ele.postid} got key")
        newpath=pathlib.Path(re.sub("\.part$","",str(item["path"]),re.IGNORECASE))
        log.debug(f"Media:{ele.id} Post:{ele.postid} [attempt {attempt.get()}/{constants.NUM_TRIES}] renaming {pathlib.Path(item['path']).absolute()} -> {newpath}")   
        subprocess.run([config_.get_mp4decrypt(config_.read_config()),"--key",key,str(item["path"]),str(newpath)])
        pathlib.Path(item["path"]).unlink(missing_ok=True)
        item["path"]=newpath
    path_to_file.unlink(missing_ok=True)
   
    ffmpeg.output( ffmpeg.input(str(video["path"])), ffmpeg.input(str(audio["path"])), str(path_to_file),codec='copy',loglevel="quiet").overwrite_output().run(capture_stdout=True,cmd=config_.get_ffmpeg(config_.read_config()))
    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        log.debug(f"Media:{ele.id} Post:{ele.postid} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        log.debug(f"Media:{ele.id} Post:{ele.postid} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        operations.write_media_table(ele,path_to_file,model_id,username)
    return ele.mediatype,total

async def key_helper(pssh,licence_url,id):
    out=cache.get(licence_url)
    log.debug(f"ID:{id} pssh: {pssh!=None}")
    log.debug(f"ID:{id} licence: {licence_url}")
    if not out:
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license': str(httpx.URL(licence_url)),
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': '',
            'proxy': '',
            'cache': True,
        }


        
        async with httpx.AsyncClient(http2=True, follow_redirects=True, timeout=None) as c: 
            r=await c.post('https://cdrm-project.com/wv',json=json_data)
            log.debug(f"ID:{id} key_response: {r.content.decode()}")
            soup = BeautifulSoup(r.content, 'html.parser')
            out=soup.find("li").contents[0]
            cache.set(licence_url,out, expire=2592000)
            cache.close()
    return out
        


  
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
def createfilename(ele,username,model_id,ext):
    if ele.responsetype =="profile":
        return "{filename}.{ext}".format(ext=ext,filename=ele.filename)
    return (config_.get_fileformat(config_.read_config())).format(filename=ele.filename,sitename="Onlyfans",site_name="Onlyfans",post_id=ele.id_,media_id=ele.id,first_letter=username[0],mediatype=ele.mediatype,value=ele.value,text=ele.text_,date=arrow.get(ele.postdate).format(config_.get_date(config_.read_config())),ext=ext,model_username=username,model_id=model_id,responsetype=ele.responsetype) 





