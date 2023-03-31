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

import httpx
from rich.console import Console
console=Console()
from tqdm.asyncio import tqdm
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from tenacity import retry,stop_after_attempt,wait_random

from .auth import add_cookies
from .config import read_config
from .dates import convert_date_to_timestamp
from .separate import separate_by_id
from ..db import operations
from .paths import set_directory
from ..utils import auth


config = read_config()['config']


async def process_dicts(headers, username, model_id, medialist,forced=False,outpath=None):
    if medialist:
        operations.create_database(model_id)
        if not forced:
            media_ids = operations.get_media_ids(model_id)
            medialist = separate_by_id(medialist, media_ids)
            console.print(f"Skipping previously downloaded\nPosts left for download {len(medialist)}")
        else:
            print("forcing all downloads")
        file_size_limit = config.get('file_size_limit')
        global sem
        sem = asyncio.Semaphore(8)
        async with httpx.AsyncClient(headers=headers, timeout=None) as c:
            add_cookies(c)
            aws=[]
            photo_count = 0
            video_count = 0
            skipped = 0
            total_bytes_downloaded = 0
            data = 0
            desc = 'Progress: ({p_count} photos, {v_count} videos, {skipped} skipped || {data})'    
            root= pathlib.Path((outpath or config.get('save_location') or pathlib.Path.cwd()))
            print(f"Downloading to {pathlib.Path(root,username)}")
            with tqdm(desc=desc.format(p_count=photo_count, v_count=video_count, skipped=skipped, data=data), total=len(aws), colour='cyan', leave=True) as main_bar:   
                for ele in medialist:
                    urldictHelper(ele)
                    filename=createfilename(ele["url"],username,model_id,ele["date"],ele["id"],ele["mediatype"],ele["text"],ele["count"])
                    with set_directory(str(pathlib.Path(root,username,ele["responsetype"].capitalize(),ele["mediatype"].capitalize()))):
                        aws.append(asyncio.create_task(download(c,ele["url"],filename,pathlib.Path(".").absolute() ,ele["mediatype"],model_id, file_size_limit, ele["date"],ele["id"],forced=False)))
                for coro in asyncio.as_completed(aws):
                        try:
                            media_type, num_bytes_downloaded = await coro
                        except Exception as e:
                            media_type = None
                            num_bytes_downloaded = 0
                            console.print(e)

                        total_bytes_downloaded += num_bytes_downloaded
                        data = convert_num_bytes(total_bytes_downloaded)

                        if media_type == 'photo' or media_type == "gif":
                            photo_count += 1
                            main_bar.set_description(
                                desc.format(
                                    p_count=photo_count, v_count=video_count, skipped=skipped, data=data), refresh=False)

                        elif media_type == 'video':
                            video_count += 1
                            main_bar.set_description(
                                desc.format(
                                    p_count=photo_count, v_count=video_count, skipped=skipped, data=data), refresh=False)

                        elif media_type == 'skipped':
                            skipped += 1
                            main_bar.set_description(
                                desc.format(
                                    p_count=photo_count, v_count=video_count, skipped=skipped, data=data), refresh=False)

                        main_bar.update()


def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
      return '0 B'
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f'{round(num_bytes / 10**9, 2)} GB'
    return f'{round(num_bytes / 10 ** 6, 2)} MB'

@retry(stop=stop_after_attempt(5),wait=wait_random(min=20, max=40),reraise=True)   
async def download(client,url,filename,path,media_type,model_id,file_size_limit,date=None,id_=None,forced=False):
    async with sem:  
        async with client.stream('GET',url) as r:
            if not r.is_error:
                rheaders=r.headers
                total = int(rheaders['Content-Length'])
                if file_size_limit and total > int(file_size_limit): 
                        return 'skipped', 1       
                content_type = rheaders.get("content-type").split('/')[-1]
                path_to_file = pathlib.Path(path,f"{filename}.{content_type}")
                with set_directory(pathlib.Path(pathlib.Path(__file__).parents[2],".tempmedia")):
                    temp=f"{filename}.{content_type}"
                    pathlib.Path(temp).unlink(missing_ok=True)
                    with open(temp, 'wb') as f:
                        with tqdm(desc=temp ,total=total, unit_scale=True, unit_divisor=1024, unit='B', leave=False) as bar:
                            num_bytes_downloaded = r.num_bytes_downloaded
                            async for chunk in r.aiter_bytes(chunk_size=1024):
                                f.write(chunk)
                                bar.update(
                                    r.num_bytes_downloaded - num_bytes_downloaded)
                                num_bytes_downloaded = r.num_bytes_downloaded
                 
                    
                    if pathlib.Path(temp).exists() and(total-pathlib.Path(temp).stat().st_size<=1000):
                        shutil.move(temp,path_to_file)
                        if date:
                            set_time(path_to_file, convert_date_to_timestamp(date))

                        if id_:
                            data = (id_, filename)
                            operations.write_from_data(data, model_id)
                        return media_type,total
                    else:
                        return 'skipped', 1
            else:
                r.raise_for_status()

async def process_dicts_paid(headers,username,model_id,medialist,forced=False,outpath=None):
 """Takes a list of purchased content and downloads it."""
 if medialist:
        operations.create_paid_database(model_id)
        if not forced:
            media_ids = operations.get_paid_media_ids(model_id)
            medialist = separate_by_id(medialist, media_ids)
            console.print(f"Skipping previously downloaded\nPaid content left for download {len(medialist)}")
        else:
            print("forcing all downloads")
        file_size_limit = config.get('file_size_limit')
        global sem
        sem = asyncio.Semaphore(8)
        # Added pool limit:
        async with httpx.AsyncClient(http2=True, headers=headers, follow_redirects=True, timeout=None) as c: 
            auth.add_cookies(c)
            aws=[]
            photo_count = 0
            video_count = 0
            skipped = 0
            total_bytes_downloaded = 0
            data = 0
            desc = 'Progress: ({p_count} photos, {v_count} videos, {skipped} skipped || {data})'   
            root= pathlib.Path((outpath or config.get('save_location') or pathlib.Path.cwd()))
            print(f"Downloading to {pathlib.Path(root,username)}")
            with tqdm(desc=desc.format(p_count=photo_count, v_count=video_count, skipped=skipped, data=data), total=len(aws), colour='cyan', leave=True) as main_bar: 
                for ele in medialist:
                    urldictHelper(ele)
                    filename=createfilename(ele["url"],username,model_id,ele["date"],ele["id"],ele["mediatype"],ele["text"],ele["count"])
                    with set_directory(pathlib.Path(root,username, "Paid",ele["mediatype"].capitalize())):
                        aws.append(asyncio.create_task(download_paid(c,ele["url"],filename,pathlib.Path(".").absolute(),ele["mediatype"],model_id, file_size_limit,ele["id"]
                        ,forced=forced)))
                for coro in asyncio.as_completed(aws):
                        try:
                            media_type, num_bytes_downloaded = await coro
                        except Exception as e:
                            media_type = None
                            num_bytes_downloaded = 0
                            console.print(e)

                        total_bytes_downloaded += num_bytes_downloaded
                        data = convert_num_bytes(total_bytes_downloaded)

                        if media_type == 'photo' or media_type == "gif":
                            photo_count += 1
                            main_bar.set_description(
                                desc.format(
                                    p_count=photo_count, v_count=video_count, skipped=skipped, data=data), refresh=False)

                        elif media_type == 'video':
                            video_count += 1
                            main_bar.set_description(
                                desc.format(
                                    p_count=photo_count, v_count=video_count, skipped=skipped, data=data), refresh=False)

                        elif media_type == 'skipped':
                            skipped += 1
                            main_bar.set_description(
                                desc.format(
                                    p_count=photo_count, v_count=video_count, skipped=skipped, data=data), refresh=False)

                        main_bar.update()


@retry(stop=stop_after_attempt(5),wait=wait_random(min=20, max=40),reraise=True)                    
async def download_paid(client,url,filename,path,media_type,model_id,file_size_limit,_id,forced=False):  
    async with sem:  
        async with client.stream('GET', url) as r:
            if not r.is_error:            
                rheaders=r.headers
                total = int(rheaders["Content-Length"])
                if file_size_limit and total>int(file_size_limit):
                    return 'skipped', 1
                content_type = rheaders.get("content-type").split('/')[-1]
                path_to_file = pathlib.Path(path,f"{filename}.{content_type}")
                with set_directory(pathlib.Path(pathlib.Path(__file__).parents[2],".tempmedia")):
                    temp=f"{filename}.{content_type}"
                    pathlib.Path(temp).unlink(missing_ok=True)
                    with open(temp, 'wb') as f:
                        with tqdm(desc=temp,total=total, unit_scale=True, unit_divisor=1024, unit="B",leave=False) as bar:
                                num_bytes_downloaded = r.num_bytes_downloaded
                                async for chunk in r.aiter_bytes(chunk_size=1024):
                                    f.write(chunk)
                                    bar.update(r.num_bytes_downloaded - num_bytes_downloaded)
                                    num_bytes_downloaded = r.num_bytes_downloaded
                    if pathlib.Path(temp).exists() and(total-pathlib.Path(temp).stat().st_size<=1000):
                        shutil.move(temp,path_to_file)
                        if _id:
                            operations.paid_write_from_data(_id,model_id)
                        return media_type,total
                    else:
                        return 'skipped', 1

            else:
                r.raise_for_status()

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
def createfilename(url,username,model_id=None,date=None,id_=None,media_type=None,text=None,count=None):
    return url.split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ ")

def urldictHelper(data):
    if data.get("reponsetype")=="post":
        data["responesetype"]="posts"
    if data.get("mediatype")=="photo" or data.get("mediatype")=="gif" :
        data["mediatype"]="images"