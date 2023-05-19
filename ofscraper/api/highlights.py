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
import logging
import httpx
from tenacity import retry,stop_after_attempt,wait_random
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
log=logging.getLogger(__package__)




@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_highlights(headers, user_id) -> list:
    with httpx.Client(http2=True, headers=headers) as c:
        url_stories = constants.highlightsWithStoriesEP.format(user_id)
        url_story = constants.highlightsWithAStoryEP.format(user_id)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url_stories, headers))
        r_multiple = c.get(url_stories, timeout=None)

        c.headers.update(auth.create_sign(url_story, headers))
        r_one = c.get(url_story, timeout=None)

        # highlights_, stories
        if not r_multiple.is_error and not r_one.is_error:
            log.debug(f"[bold]Highlight Post Count without Dupes[/bold] {len(r_multiple.json())} found")
            log.debug(f"[bold]Story Post Count without Dupes[/bold] {len(r_one.json())} found")
            return get_highlightList(r_multiple.json()),r_one.json()

        r_multiple.raise_for_status()
        r_one.raise_for_status()

def get_highlightList(data):
    for ele in list(filter(lambda x:isinstance(x,list),data.values())):
        if len(list(filter(lambda x:isinstance(x.get("id"),int) and data.get("hasMore")!=None,ele)))>0:
               return ele
    return []


    









