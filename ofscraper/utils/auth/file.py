r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import json

from rich.console import Console

import ofscraper.utils.auth.make as make
import ofscraper.utils.auth.schema as auth_schema
import ofscraper.utils.auth.utils.context as auth_context
import ofscraper.utils.auth.utils.dict as auth_dict
import ofscraper.utils.paths.common as common_paths

console = Console()


def read_auth():
    while True:
        auth = None
        with auth_context.auth_context():
            old_auth = auth_dict.get_auth_dict()
            auth = auth_schema.auth_schema(old_auth)
            if auth_schema.auth_key_missing(old_auth):
                auth = write_auth(auth)
            if auth_schema.auth_key_null(auth):
                auth = make.make_auth(auth)
            break
    return auth


def edit_auth():
    while True:
        auth = None
        with auth_context.auth_context():
            auth = auth_dict.get_auth_dict()
            auth = make.make_auth(auth)
            console.print("Your `auth.json` file has been edited")
            break
    return auth


def write_auth(auth):
    if isinstance(auth, dict):
        auth = json.dumps(auth, indent=4)
    with open(common_paths.get_auth_file(), "w") as f:
        f.write(auth)
    return auth_dict.get_auth_dict(auth)
