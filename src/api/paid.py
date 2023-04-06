r"""
               _          __
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|
                  |___/                                                        |_|
"""
from urllib.request import urlopen

from rich.console import Console
console=Console()
from ..constants import purchased_contentEP
from ..utils import auth
import httpx
from ..utils.config import read_config


config = read_config()['config']
paid_content_list_name = 'list'














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
                console.print(f"Scraping, Scraping isn't frozen. It takes time.\nScraped Page: {count}")
                if "hasMore" in r.json():
                    hasMore = r.json()['hasMore']
                    count=count+1
                media_to_download.extend(list(filter(lambda x:isinstance(x,list),r.json().values()))[0])
    return media_to_download

def parse_paid(paid):
    media_to_download=[]
    for item in paid:
        for count,media in enumerate(list(filter(lambda x:x.get("source"),item['media']))):
            media_to_download.append({"id":media["id"],"mediatype":media["type"],"url":media["source"]["source"],"count":count+1,"text":item["text"],"date":item["createdAt"],"responsetype":item["responseType"],"postid":item["id"],"value":"free" if item.get("IsFree") else "paid","data":item})
    return media_to_download





