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
import sys
import shutil
import traceback
import re
import httpx
import os
from rich.console import Console
console=Console()
from tqdm.asyncio import tqdm
import arrow
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from tenacity import retry,stop_after_attempt,wait_random

from .auth import add_cookies
from .config import read_config
from .separate import separate_by_id
from ..db import operations
from .paths import set_directory
from ..utils import auth
from ..constants import configPath
from ..utils.profiles import get_current_profile



config = read_config()['config']


async def process_dicts(username, model_id, medialist,forced=False,outpath=None):
    if medialist:
        if not forced:
            media_ids = set(operations.get_media_ids(model_id,username))
            medialist = separate_by_id(medialist, media_ids)
            console.print(f"Skipping previously downloaded\nMedia left for download {len(medialist)}")
        else:
            print("forcing all downloads")
        file_size_limit = config.get('file_size_limit')
        global sem
        sem = asyncio.Semaphore(8)
      
        aws=[]
        photo_count = 0
        video_count = 0
        audio_count=0
        skipped = 0
        total_bytes_downloaded = 0
        data = 0
        desc = 'Progress: ({p_count} photos, {v_count} videos, {skipped} skipped || {sumcount}/{mediacount}||{data})'    
        print(f"\nDownloading to {(config.get('save_location') or pathlib.Path.home()/'ofscraper')}/{(config.get('dir_format') or '{model_username}/{responsetype}/{mediatype}')}\n\n")

        with tqdm(desc=desc.format(p_count=photo_count, v_count=video_count, skipped=skipped,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped,data=data), total=len(aws), colour='cyan', leave=True) as main_bar:   
            for ele in medialist:
                with set_directory(getmediadir(ele,username,model_id)):

                    aws.append(asyncio.create_task(download(ele,pathlib.Path(".").absolute() ,model_id, username,file_size_limit)))
            for coro in asyncio.as_completed(aws):
                    try:
                        media_type, num_bytes_downloaded = await coro
                    except Exception as e:
                        media_type = None
                        num_bytes_downloaded = 0
                        console.print(e)

                    total_bytes_downloaded += num_bytes_downloaded
                    data = convert_num_bytes(total_bytes_downloaded)
                    if media_type == 'images':
                        photo_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    elif media_type == 'videos':
                        video_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    elif media_type == 'audios':
                        audio_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    elif media_type == 'skipped':
                        skipped += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    main_bar.update()


def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
      return '0 B'
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f'{round(num_bytes / 10**9, 2)} GB'
    return f'{round(num_bytes / 10 ** 6, 2)} MB'

@retry(stop=stop_after_attempt(5),wait=wait_random(min=20, max=40),reraise=True)  
async def download(ele,path,model_id,username,file_size_limit,id_=None):
    url=ele['url']
    media_type=ele['mediatype']
    id_=ele.get("id")
    bar=None
    temp=None

    try:
        async with sem:
            async with httpx.AsyncClient(http2=True, headers = auth.make_headers(auth.read_auth()), follow_redirects=True, timeout=None) as c: 
                auth.add_cookies(c)        
                async with c.stream('GET',url) as r:
                    if not r.is_error:
                        rheaders=r.headers
                        total = int(rheaders['Content-Length'])
                        if file_size_limit and total > int(file_size_limit): 
                                return 'skipped', 1       
                        content_type = rheaders.get("content-type").split('/')[-1]
                        filename=createfilename(ele,username,model_id,content_type)
                        path_to_file = trunicate(pathlib.Path(path,f"{filename}"))
                        with set_directory(pathlib.Path(pathlib.Path.home(),configPath,get_current_profile(),".tempmedia")):
                            temp=trunicate(f"{filename}")
                            pathlib.Path(temp).unlink(missing_ok=True)
                            with open(temp, 'wb') as f:
                                pathstr=str(temp)
                                bar=tqdm(desc=(pathstr[:50] + '....') if len(pathstr) > 50 else pathstr ,total=total, unit_scale=True, unit_divisor=1024, unit='B', leave=False)
                                num_bytes_downloaded = r.num_bytes_downloaded
                                async for chunk in r.aiter_bytes(chunk_size=1024):
                                    f.write(chunk)
                                    bar.update(
                                        r.num_bytes_downloaded - num_bytes_downloaded)
                                    num_bytes_downloaded = r.num_bytes_downloaded
                        
                            
                            if pathlib.Path(temp).exists() and  abs(total-pathlib.Path(temp).stat().st_size)<=1000:
                                shutil.move(temp,path_to_file)
                                if id_:
                                    operations.write_media(ele,path_to_file,model_id,username)
                                return media_type,total
                            else:
                                return 'skipped', 1
                    else:
                        r.raise_for_status()
    except Exception as e:
        if not r or r.status_code==200:
            print(traceback.format_exc())
        return 'skipped', 1
    finally:
        if bar:
            bar.close()
        if temp:
            pathlib.Path(temp).unlink(missing_ok=True)
        

async def process_dicts_paid(username,model_id,medialist,forced=False):
 """Takes a list of purchased content and downloads it."""
 if medialist:
        if not forced:
            media_ids = set(operations.get_media_ids(model_id,username))
            medialist = separate_by_id(medialist, media_ids)
            console.print(f"Skipping previously downloaded\nPaid media content left for download {len(medialist)}")
        else:
            print("forcing all downloads")
        file_size_limit = config.get('file_size_limit')
        global sem
        sem = asyncio.Semaphore(8)
        aws=[]
        photo_count = 0
        video_count = 0
        audio_count=0
        skipped = 0
        total_bytes_downloaded = 0
        data = 0
        desc = 'Progress: ({p_count} photos, {v_count} videos, {skipped} skipped || {data})'   
        print(f"\nDownloading to {(config.get('save_location') or pathlib.Path.home()/'ofscraper')}/{(config.get('dir_format') or '{model_username}/{responsetype}/{mediatype}')}\n\n")

        with tqdm(desc=desc.format(p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), total=len(aws), colour='cyan', leave=True) as main_bar: 
            for ele in medialist:
                with set_directory(getmediadir(ele,username,model_id)):
                    aws.append(asyncio.create_task(download_paid(ele,pathlib.Path(".").absolute() ,model_id, username,file_size_limit)))
            for coro in asyncio.as_completed(aws):
                    try:
                        media_type, num_bytes_downloaded = await coro
                    except Exception as e:
                        media_type = None
                        num_bytes_downloaded = 0
                        console.print(e)

                    total_bytes_downloaded += num_bytes_downloaded
                    data = convert_num_bytes(total_bytes_downloaded)

                    if media_type == 'images':
                        photo_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=False)

                    elif media_type == 'audios':
                        audio_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=False)                        
                    elif media_type == 'videos':
                        video_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=False)

                    elif media_type == 'skipped':
                        skipped += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=False)

                    main_bar.update()


@retry(stop=stop_after_attempt(5),wait=wait_random(min=20, max=40),reraise=True)                    
async def download_paid(ele,path,model_id,username,file_size_limit,id_=None):  
    url=ele['url']
    media_type=ele['mediatype']
    id_=ele['id']
    bar=None
    temp=None
    try:
        async with sem:  
            async with httpx.AsyncClient(http2=True, headers = auth.make_headers(auth.read_auth()), follow_redirects=True, timeout=None) as c: 
                auth.add_cookies(c)     
                async with c.stream('GET', url) as r:
                    if not r.is_error:            
                        rheaders=r.headers
                        total = int(rheaders["Content-Length"])
                        if file_size_limit and total>int(file_size_limit):
                            return 'skipped', 1
                        content_type = rheaders.get("content-type").split('/')[-1]
                        filename=createfilename(ele,username,model_id,content_type)
                        path_to_file = trunicate(pathlib.Path(path,f"{filename}"))
                        with set_directory(pathlib.Path(pathlib.Path.home(),configPath,get_current_profile(),".tempmedia")):
                            temp=trunicate(f"{filename}")
                            pathlib.Path(temp).unlink(missing_ok=True)
                            with open(temp, 'wb') as f:
                                pathstr=str(temp)
                                bar=tqdm(desc=(pathstr[:10] + '....') if len(pathstr) > 10 else pathstr,total=total, unit_scale=True, unit_divisor=1024, unit="B",leave=False) 
                                num_bytes_downloaded = r.num_bytes_downloaded
                                async for chunk in r.aiter_bytes(chunk_size=1024):
                                    f.write(chunk)
                                    bar.update(r.num_bytes_downloaded - num_bytes_downloaded)
                                    num_bytes_downloaded = r.num_bytes_downloaded
                            if pathlib.Path(temp).exists() and(total-pathlib.Path(temp).stat().st_size<=1000):
                                shutil.move(temp,path_to_file)
                                if id_:
                                    operations.write_media(ele,path_to_file,model_id,username)
                                return media_type,total
                            else:
                                return 'skipped', 1

                    else:
                        r.raise_for_status()
                        
    except Exception as e:
        if not r or r.status_code==200:
            print(traceback.format_exc())
        return 'skipped', 1
    finally:
        if bar:
            bar.close()
        if temp:
            pathlib.Path(temp).unlink(missing_ok=True)
        
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
    filename=ele["url"].split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ ")
    if ele.get("responsetype") in "profile":
        return filename
    
    return (config.get('file_format') or '{filename}.{ext}').format(filename=filename,sitename="Onlyfans",post_id=ele["postid"],media_id=ele["id"],first_letter=username[0],media_type=ele["mediatype"],value=ele["value"],text=texthelper(ele.get("text") or filename,ele),date=arrow.get(ele['date']).format(config.get('date')),ext=ext,model_username=username,model_id=model_id,responsetype=ele["responsetype"])

def texthelper(text,ele):    
    count=ele["count"]
    length=int(config.get("textlength") or 0)
    if length!=0:
        text=text[0:length]
    if (len(ele["data"].get("media",[]))>1) or ele.get("responsetype") in ["stories","highlights"]:
        text= f"{text}{count}"
    # text=re.sub("[^\x00-\x7F]","",text)
    text=re.sub("<[^>]*>", "",text)
    text=re.sub('[\n<>:"/\|?*]+', '', text)
    text=re.sub(" +"," ",text)
    return text
    

   




def getmediadir(ele,username,model_id):
    root= pathlib.Path((config.get('save_location') or pathlib.Path.home()/"ofscraper"))
    downloadDir=(config.get('dir_format') or "{model_username}/{responsetype}/{mediatype}").format(sitename="onlyfans",first_letter=username[0].capitalize(),model_id=model_id,model_username=username,responsetype=ele['responsetype'].capitalize(),mediatype=ele['mediatype'].capitalize(),value=ele['value'].capitalize(),date=arrow.get(ele['date']).format(config.get('date')))
    return root /downloadDir

def trunicate(path):
    if platform.system() == 'Windows' and len(path)>256:
        return path[0:256]
    elif platform.system() == 'Linux':
        dir=pathlib.Path(path).parent
        file=pathlib.Path(path).name.encode("utf8")[:255].decode("utf8", "ignore")
        return pathlib.Path(dir,file)
    return path