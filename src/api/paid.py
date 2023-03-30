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
from rich.console import Console
console=Console()
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







def scrape_paid(username):
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
            url = purchased_contentEP.format(offset,username)
            offset += 10
            c.headers.update(auth.create_sign(url, headers))
            r = c.get(url, timeout=None)
            if not r.is_error:
                console.print(f"Scraping, Scraping isn't frozen. It takes time.\nScraped Page:{count}")
                if "hasMore" in r.json():
                    hasMore = r.json()['hasMore']
                    count=count+1
                # THIS NEEDS TO BE REWORKED TO WORK LIKE HIGHLIGHTS AND FIGURE OUT THE LIST NAME HAVEN'T HAD TIME.
                for item in r.json()[paid_content_list_name]:
                    media_to_download.append(item)
    return media_to_download

def parse_paid(paid):
    media_to_download=[]
    for item in paid:
        for count,media in enumerate(list(filter(lambda x:x.get("source"),item['media']))):
            media_to_download.append({"id":media["id"],"mediatype":media["type"],"url":media["source"]["source"],"count":count+1,"text":item["text"],"date":item["createdAt"],"data":item})
    return media_to_download





