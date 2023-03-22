r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

import httpx


from ..constants import (
    timelineEP, timelineNextEP,
    timelinePinnedEP,
    archivedEP, archivedNextEP
)
from ..utils import auth


def scrape_pinned_posts(headers, model_id) -> list:
    with httpx.Client(http2=True, headers=headers) as c:
        url = timelinePinnedEP.format(model_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['list']
        r.raise_for_status()


def scrape_timeline_posts(headers, model_id, timestamp=0) -> list:
    ep = timelineNextEP if timestamp else timelineEP
    url = ep.format(model_id, timestamp)

    with httpx.Client(http2=True, headers=headers) as c:
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            posts = r.json()['list']
            if not posts:
                return posts
            posts += scrape_timeline_posts(
                headers, model_id, posts[-1]['postedAtPrecise'])
            return posts
        r.raise_for_status()


def scrape_archived_posts(headers, model_id, timestamp=0) -> list:
    ep = archivedNextEP if timestamp else archivedEP
    url = ep.format(model_id, timestamp)

    with httpx.Client(http2=True, headers=headers) as c:
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            posts = r.json()['list']
            if not posts:
                return posts
            posts += scrape_archived_posts(
                headers, model_id, posts[-1]['postedAtPrecise'])
            return posts
        r.raise_for_status()


def parse_posts(posts: list):
    data = list(filter( lambda x:x.get('media')!=None,posts))

    urls = [
        (i['info']['source']['source'], i['createdAt'], i['id'], i['type'],m["text"],"posts",count+1) for m in data for count,i in enumerate(m["media"]) if i['canView']]
    return urls
