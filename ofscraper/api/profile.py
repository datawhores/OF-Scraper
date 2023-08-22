r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import logging
import contextvars

from typing import Union
from rich.console import Console
from tenacity import retry,stop_after_attempt,wait_random,retry_if_not_exception_type
from ..constants import profileEP,NUM_TRIES,HOURLY_EXPIRY,DAILY_EXPIRY
from ..utils import auth, encoding
from xxhash import xxh128
from diskcache import Cache
from ..utils.paths import getcachepath
import ofscraper.constants as constants
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.config as config_


log=logging.getLogger("shared")
console=Console()
attempt = contextvars.ContextVar("attempt")




# can get profile from username or id
def scrape_profile(username:Union[int, str]) -> dict:
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return scrape_profile_helper(c,username)


  
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
def scrape_profile_helper(c,username:Union[int, str]):

    cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    id=cache.get(f"username_{username}",None)
    log.trace(f"username date: {id}")
    if id:
        return id
    attempt.set(attempt.get(0) + 1)
    log.info(f"Attempt {attempt.get()}/{constants.NUM_TRIES} to get profile {username}")
    with c.requests(profileEP.format(username))() as r:
        if r.ok:
            attempt.set(0)
            cache.set(f"username_{username}",r.json(),int(HOURLY_EXPIRY*2))
            cache.close()
            log.trace(f"username date: {r.json()}")
            return r.json()
        elif r.status==404:
            attempt.set(0)
            return {"username":"modeldeleted"}
        else:
              log.debug(f"[bold]profile response status code:[/bold]{r.status}")
              log.debug(f"[bold]profile response:[/bold] {r.text_()}")
              log.debug(f"[bold]profile headers:[/bold] {r.headers}")
              r.raise_for_status()




def parse_profile(profile: dict) -> tuple:
    media = []
    media.append(profile.get('avatar'))
    media.append(profile.get('header'))
    media.append(profile.get('profile'))
    media=list(filter(lambda x:x!=None,media))

    output=[]
    for ele in media:
        output.append({"url":ele,"responsetype":"profile","mediatype":"photo","value":"free","createdAt":profile["joinDate"],"text":profile["about"],"id":xxh128(ele).hexdigest(),"mediaid":xxh128(ele[:-1]).hexdigest()})


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


def get_id( username):
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return get_id_helper(c,username)

    
        
        

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
def get_id_helper(c,username):
    cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))   
    id=cache.get(f"model_id_{username}",None)
    if id:
        return id
    with c.requests(profileEP.format(username))() as r:
        if r.ok:
            id=r.json()['id']
            cache.set(f"model_id_{username}",id,DAILY_EXPIRY)
            cache.close()
            return id
        else:
            log.debug(f"[bold]id response status code:[/bold]{r.status}")
            log.debug(f"[bold]id response:[/bold] {r.text_()}")
            log.debug(f"[bold]id headers:[/bold] {r.headers}")
            r.raise_for_status()
