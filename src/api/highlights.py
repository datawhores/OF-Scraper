r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

import asyncio
from itertools import chain

import httpx

from ..constants import highlightsWithStoriesEP, highlightsWithAStoryEP, storyEP
from ..utils import auth


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
    for item in highlights:
        if isinstance(highlights[item],list):
            for highlight in highlights[item]:
                if 'id' in highlight:
                    if isinstance(highlight['id'],int):
                        ids_location = highlights[item]

    if 'hasMore' in highlights:
        if not highlights['hasMore']:
            return []
    else:
        print('HasMore error with highlights.')
        input("Press Enter to continue.")
        return[]
    try:
        # highlight_ids = [highlight['id'] for highlight in ids_location]
        #highlight_ids = [highlight['id'] for highlight in highlights['list']]
        return [highlight['id'] for highlight in ids_location]
    except Exception as e:
        print("{} \n \n \n The above exception was encountered while trying to save highlights.".format(e))
        input("Press Enter to continue.")
        return[]




async def process_highlights_ids(headers, ids: list) -> list:
    if not ids:
        return []

    tasks = [scrape_story(headers, id_) for id_ in ids]
    results = await asyncio.gather(*tasks)
    return list(chain.from_iterable(results))


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

    
    urls = [(m['files']['source']['url'], m.get("createdAt") or story.get("createdAt") , m['id'], m['type'],m.get("text"),"stories",count+1)
            for story in stories for count,m in enumerate(story["media"]) if m['canView']]
    return urls
