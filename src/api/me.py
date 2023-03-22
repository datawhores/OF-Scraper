r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

import httpx

from ..constants import meEP
from ..utils import auth, encoding


def scrape_user(headers):
    with httpx.Client(http2=True, headers=headers) as c:
        url = meEP

        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            return r.json()
        r.raise_for_status()


def parse_user(profile):
    name = encoding.encode_utf_16(profile['name'])
    username = profile['username']
    subscribe_count = profile['subscribesCount']
    return (name, username, subscribe_count)


def print_user(name, username):
    print(f'Welcome, {name} | {username}')
