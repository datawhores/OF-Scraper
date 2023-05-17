r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import logging
import httpx
from rich.console import Console
from tenacity import retry,stop_after_attempt,wait_random
from ..constants import profileEP,NUM_TRIES
from ..utils import auth, encoding
from xxhash import xxh32

log=logging.getLogger(__package__)
console=Console()

@retry(stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
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
        output.append({"url":ele,"responsetype":"profile","mediatype":"photo","value":"free","createdAt":profile["joinDate"],"text":profile["about"],"id":xxh32(ele).hexdigest()})


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
    log.info(final_fmt.format(*info))


@retry(stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=5, max=20),reraise=True)   
def get_id(headers, username):
    with httpx.Client(http2=True, headers=headers) as c:
        url = profileEP.format(username)

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()['id']
        r.raise_for_status()


        