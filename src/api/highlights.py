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


from ..constants import highlightsWithStoriesEP, highlightsWithAStoryEP, storyEP
from ..utils import auth


@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
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
            return r_multiple.json(), r_one.json()

        r_multiple.raise_for_status()
        r_one.raise_for_status()




def parse_highlights(highlights: list) -> list:
    #This needs further work but will work for now. I was thinking of adding full recurssive ability until all conditions are met.
    #This means that whenever onlyfans changes the name of the list containing the highlights it wont matter because the name is variable.
    #To break this they would have to change the conditions or in this release the layers.
    temp=[]
    for item in list(filter(lambda x:isinstance(x,list),highlights.values())):
        for highlight in list(filter(lambda x:x.get("id") and isinstance(x['id'],int),item)):
            temp.append(highlight)
    output=[]
    for count,item in enumerate(temp):
        output.append({"id":item["id"],"date":item["createdAt"],"text":item["title"],"responsetype":"highlight","count":count+1,"url":item["cover"],"mediatype":"photo","data":item})
    return output
async def process_highlights_ids(headers, ids: list) -> list:
    if not ids:
        return []

    tasks = [scrape_story(headers, id_) for id_ in ids]
    results = await asyncio.gather(*tasks)
    return list(chain.from_iterable(results))


@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
async def scrape_story(headers, story_id: int) -> list:
    async with httpx.AsyncClient(http2=True, headers=headers) as c:
        url = storyEP.format(story_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = await c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['stories']
        r.raise_for_status()


def parse_stories(stories: list):
    output=[]
    for story in stories:
        for media in story["media"]:
            output.append({"url":media["files"]["source"]["url"],"id":media["id"],"date":media["createdAt"],"responsetype":"stories","count":1,"text":None,"mediatype":media["type"],"data":media})
    return output


