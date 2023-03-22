r"""
               _          __
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|
                  |___/                                                        |_|
"""
from urllib.request import urlopen
import asyncio
import math
import tempfile
import shutil
import os

from ..constants import purchased_contentEP
from ..utils import auth
import httpx
import pathlib
from ..utils.config import read_config
from ..utils.paths import set_directory
import sqlite3 as sql
from tqdm import tqdm
from ..db import operations
from ..utils.separate import separate_by_id

config = read_config()['config']
paid_content_list_name = 'list'




root= pathlib.Path((config.get('save_location') or pathlib.Path.cwd()))








# def add_to_db(urlbase):
#     code=md5(urlbase.encode())

#     """Returns True if hash was not in the database and file can continue."""
    
#     db.commit()
#     cursor.execute(f"SELECT * FROM hashes WHERE hash='{code.hexdigest()}'")
#     results = cursor.fetchall()
#     if len(results) > 0:
#         return False
#     cursor.execute("""INSERT INTO hashes(hash,file_name) VALUES(?,?)""",(code.hexdigest(),urlbase))
#     db.commit()
#     return True







def scrape_paid():
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list."""
    media_to_download = []
    offset = 0
    hasMore = True
    headers = auth.make_headers(auth.read_auth())
    count=1
    with httpx.Client(http2=True, headers=headers, follow_redirects=True) as c:
        while hasMore:
            headers = auth.make_headers(auth.read_auth())
            auth.add_cookies(c)
            url = purchased_contentEP.format(offset)
            offset += 10
            c.headers.update(auth.create_sign(url, headers))
            r = c.get(url, timeout=None)
            if not r.is_error:
                print(f"Scraping, Scraping isn't frozen. It takes time.\nScraped Page:{count}")
                if "hasMore" in r.json():
                    hasMore = r.json()['hasMore']
                    count=count+1
                # THIS NEEDS TO BE REWORKED TO WORK LIKE HIGHLIGHTS AND FIGURE OUT THE LIST NAME HAVEN'T HAD TIME.
                for item in r.json()[paid_content_list_name]:
                    media_to_download.append(item)
    return media_to_download

def parse_paid(all_paid,model_id):
    media_to_download=[]
    items=list(filter(lambda x:(x.get("fromUser") or x.get("author"))["id"]==model_id,all_paid))
    for item in items:
        for count,i in enumerate(item['media']):
                    if "source" in i:
                        media_to_download.append((i['source']['source'],i.get("createdAt") or item.get("createdAt"),i["id"],i["type"],item["text"],item["responseType"],count+1))
    return media_to_download
async def process_dicts(headers,username,model_id,medialist,forced=False):
 """Takes a list of purchased content and downloads it."""
 if medialist:
        operations.create_paid_database(model_id)
        if not forced:
            media_ids = operations.get_paid_media_ids(model_id)
            medialist = separate_by_id(medialist, media_ids)
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
            with tqdm(desc=desc.format(p_count=photo_count, v_count=video_count, skipped=skipped, data=data), total=len(aws), colour='cyan', leave=True) as main_bar: 
                for ele in medialist:
                    filename=createfilename(ele[0],username,model_id,ele[1],ele[2],ele[3],ele[4],ele[6])
                    with set_directory(pathlib.Path(root,username, 'Paid',ele[3].capitalize())):
                        aws.append(asyncio.create_task(download_paid(c,ele[0],filename,pathlib.Path(".").absolute(),ele[3],model_id, file_size_limit,ele[2]
                        ,forced=forced)))
                for coro in asyncio.as_completed(aws):
                        try:
                            media_type, num_bytes_downloaded = await coro
                        except Exception as e:
                            media_type = None
                            num_bytes_downloaded = 0
                            print(e)

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

def createfilename(url,username,model_id=None,date=None,id_=None,media_type=None,text=None,count=None):
    return geturlbase(url)
def geturlbase(url):
    return url.split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ ")
def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
      return '0 B'
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f'{round(num_bytes / 10**9, 2)} GB'
    return f'{round(num_bytes / 10 ** 6, 2)} MB'





