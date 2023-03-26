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
from typing import Union

import httpx
from rich.console import Console
console=Console()
from revolution import Revolution

from ..api import posts
from ..constants import favoriteEP, postURL
from ..utils import auth


def get_posts(headers, model_id):
    with Revolution(desc='Getting posts...') as _:
        pinned_posts = posts.scrape_pinned_posts(headers, model_id)
        timeline_posts = posts.scrape_timeline_posts(headers, model_id)
        archived_posts = posts.scrape_archived_posts(headers, model_id)

    return pinned_posts + timeline_posts + archived_posts


def filter_for_unfavorited(posts: list) -> list:
    unfavorited_posts = [post for post in posts if 'isFavorite' in post and not post['isFavorite']]
    return unfavorited_posts


def filter_for_favorited(posts: list) -> list:
    favorited_posts = [post for post in posts if 'isFavorite' in post and post['isFavorite']]
    return favorited_posts


def get_post_ids(posts: list) -> list:
    ids = [post['id'] for post in posts if 'isOpened' in post and post['isOpened']]
    return ids


def like(headers, model_id, username, ids: list):
    _like(headers, model_id, username, ids, True)


def unlike(headers, model_id, username, ids: list):
    _like(headers, model_id, username, ids, False)


def _like(headers, model_id, username, ids: list, like_action: bool):
    title = "Liking" if like_action else "Unliking"
    with Revolution(desc=f'{title} posts...', total=len(ids)) as rev:
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
                            break
                        else:
                            _handle_err(r, postURL.format(i, username))
                    except httpx.TransportError as e:
                        _handle_err(e, postURL.format(i, username))
                rev.update()


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
    console.print(f'{status}{message}, post at {url}')
