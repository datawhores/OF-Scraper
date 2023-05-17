r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import random
import time
import logging
from typing import Union
import asyncio
import httpx
from rich.console import Console
console=Console()
from halo import Halo
from ..api import timeline
from ..constants import favoriteEP, postURL
from ..utils import auth

log=logging.getLogger(__package__)




def get_posts(headers, model_id):
    with Halo(text='Getting all timeline posts...'):
        pinned_posts = timeline.scrape_pinned_posts(headers, model_id)
        timeline_posts = asyncio.run(timeline.get_timeline_post(headers, model_id))
        archived_posts = timeline.scrape_archived_posts(headers, model_id)
    log.debug(f"[bold]Number of Post Found[/bold] {len(pinned_posts) + len(timeline_posts) + len(archived_posts)}")
    return pinned_posts + timeline_posts + archived_posts


def filter_for_unfavorited(posts: list) -> list:
    output=list(filter(lambda x:x.get("isFavorite")==False,posts))
    log.debug(f"[bold]Number of unliked post[/bold {len(output)}")
    return output




def filter_for_favorited(posts: list) -> list:
    output=list(filter(lambda x:x.get("isFavorite")==True,posts))
    log.debug(f"[bold]Number of liked post[/bold {len(output)}")
    return output



def get_post_ids(posts: list) -> list:
    valid_post=list(filter(lambda x:x.get("isOpened")==True,posts))
    return list(map(lambda x:x.get("id"),valid_post))
   


def like(headers, model_id, username, ids: list):
    _like(headers, model_id, username, ids, True)


def unlike(headers, model_id, username, ids: list):
    _like(headers, model_id, username, ids, False)


def _like(headers, model_id, username, ids: list, like_action: bool):
    title = "Liking" if like_action else "Unliking"
    with Halo(text=f'{title} posts...'):
        for i in ids:
            with httpx.Client(http2=True, headers=headers) as c:
                url = favoriteEP.format(i, model_id)

                auth.add_cookies(c)
                c.headers.update(auth.create_sign(url, headers))

                retries = 0
                while retries <= 1:
                    time.sleep(random.uniform(0.8, 0.9))
                    retries += 1
                    try:
                        r = c.post(url)
                        if not r.is_error or r.status_code == 400:
                            log.debug(f"ID: {i} Performed {'like' if like_action==True else 'unlike'} action")
                            break
                        else:
                            _handle_err(r, postURL.format(i, username))
                    except httpx.TransportError as e:
                        _handle_err(e, postURL.format(i, username))
      


def _handle_err(param: Union[httpx.Response, httpx.TransportError], url: str) -> str:
    message = 'unable to execute action'
    status = ''
    try:
        if isinstance(param, httpx.Response):
            json = param.json()
            if 'error' in json and 'message' in json['error']:
                message = json['error']['message']
            status = f'STATUS CODE {param.status_code}: '
        else:
            message = str(param)
    except:
        pass
    log.warning(f'{status}{message}, post at {url}')
