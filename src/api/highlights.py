r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
from itertools import chain

import httpx
from tenacity import retry,stop_after_attempt,wait_random


from ..constants import NUM_TRIES,highlightsWithStoriesEP, highlightsWithAStoryEP, storyEP
from ..utils import auth


@retry(stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_highlights(headers, user_id) -> list:
    with httpx.Client(http2=True, headers=headers) as c:
        url_stories = highlightsWithStoriesEP.format(user_id)
        url_story = highlightsWithAStoryEP.format(user_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url_stories, headers))
        r_multiple = c.get(url_stories, timeout=None)

        c.headers.update(auth.create_sign(url_story, headers))
        r_one = c.get(url_story, timeout=None)

        if not r_multiple.is_error and not r_one.is_error:
            return get_highlightList(r_multiple.json()),r_one.json()

        r_multiple.raise_for_status()
        r_one.raise_for_status()

def get_highlightList(data):
    for ele in list(filter(lambda x:isinstance(x,list),data.values())):
        if len(list(filter(lambda x:isinstance(x.get("id"),int) and data.get("hasMore")!=None,ele)))>0:
               return ele
    return []


    







@retry(stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
async def scrape_story(headers, story_id: int) -> list:
    async with httpx.AsyncClient(http2=True, headers=headers) as c:
        url = storyEP.format(story_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = await c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['stories']
        r.raise_for_status()



