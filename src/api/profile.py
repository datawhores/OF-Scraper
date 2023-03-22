r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

from datetime import datetime
from itertools import zip_longest

import httpx

from ..constants import profileEP
from ..utils import auth, dates, encoding


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
    if (avatar := profile['avatar']):
        media.append((avatar,"Profile"))
    if (header := profile['header']):
        media.append((header,"Header"))
    # media_urls = list(zip_longest(media, [], fillvalue=None))

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
    output=[]

    [output.append((ele[0],join_date,None,"photo",profile["about"],"profile",count+1)) for count,ele in enumerate(media)]
    return output, info



def print_profile_info(info):
    header_fmt = 'Name: {} | Username: {} | ID: {} | Joined: {}\n'
    info_fmt = '- {} posts\n -- {} photos\n -- {} videos\n -- {} audios\n- {} archived posts'
    final_fmt = header_fmt + info_fmt
    print(final_fmt.format(*info))


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
    print(
f"""
Username: {username}
- paid content {len(paid_content)}
 -- photos {len(list(filter(lambda x:x[3]=="photo",paid_content)))}
 -- videos {len(list(filter(lambda x:x[3]=="video",paid_content)))}
 -- audios {len(list(filter(lambda x:x[3]=="audio",paid_content)))}
"""
)
        