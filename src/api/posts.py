r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import httpx
from tenacity import retry,stop_after_attempt,wait_random


from ..constants import (
    timelineEP, timelineNextEP,
    timelinePinnedEP,
    archivedEP, archivedNextEP
)
from ..utils import auth

@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_pinned_posts(headers, model_id) -> list:
    with httpx.Client(http2=True, headers=headers) as c:
        url = timelinePinnedEP.format(model_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['list']
        r.raise_for_status()

@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
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


@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
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
    # [  'data']
    output=[]
    for ele in data:
        medialist=list(filter(lambda x:x["canView"],ele["media"]))
        for count,media in enumerate(medialist):
            output.append({"responsetype":ele["responseType"],"id":media["id"],"date":media["createdAt"]
            ,"text":ele["text"],"count":count+1,"url":media["source"]["source"],"mediatype":media["type"],"data":ele})
    return output



