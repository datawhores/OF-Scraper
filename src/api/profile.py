r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

from datetime import datetime
from itertools import zip_longest

import httpx
from rich.console import Console
console=Console()
from tenacity import retry,stop_after_attempt,wait_random
from ..constants import profileEP
from ..utils import auth, dates, encoding

@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_profile(headers, username) -> dict:
    with httpx.Client(http2=True, headers=headers) as c:
        url = profileEP.format(username)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(profileEP.format(username), timeout=None)
        if not r.is_error:
            return r.json()
        r.raise_for_status()


def parse_profile(profile: dict) -> tuple:
    media = []
    media.append(profile.get('avatar'))
    media.append(profile.get('profile'))
    media=list(filter(lambda x:x!=None,media))

    output=[]
    for ele in media:
        output.append({"url":ele,"responsetype":"profile","mediatype":"images","value":"free","date":profile["joinDate"]})


    name = encoding.encode_utf_16(profile['name'])
    username = profile['username']
    id_ = profile['id']
    join_date = profile['joinDate']
    posts_count = profile['postsCount']
    photos_count = profile['photosCount']
    videos_count = profile['videosCount']
    audios_count = profile['audiosCount']
    archived_posts_count = profile['archivedPostsCount']
    info = (
        name, username, id_, join_date,
        posts_count, photos_count, videos_count, audios_count, archived_posts_count)
  

    return output, info



def print_profile_info(info):
    header_fmt = 'Name: {} | Username: {} | ID: {} | Joined: {}\n'
    info_fmt = '- {} posts\n -- {} photos\n -- {} videos\n -- {} audios\n- {} archived posts'
    final_fmt = header_fmt + info_fmt
    console.print(final_fmt.format(*info))


@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
def get_id(headers, username):
    with httpx.Client(http2=True, headers=headers) as c:
        url = profileEP.format(username)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['id']
        r.raise_for_status()

def print_paid_info(paid_content,username):
    console.print(
f"""
Username: {username}
- paid content {len(paid_content)}
 -- photos {len(list(filter(lambda x:x.get("mediatype")=="photo" or x.get("mediatype")=="gif",paid_content)))}
 -- videos {len(list(filter(lambda x:x.get("mediatype")=="video",paid_content)))}
 -- audios {len(list(filter(lambda x:x.get("mediatype")=="audio" ,paid_content)))}
"""
)
        