import ofscraper.utils.auth.helpers as helpers

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

import ofscraper.utils.auth.context as auth_context
import ofscraper.utils.auth.make as make
import ofscraper.utils.auth.request as request_auth
import ofscraper.utils.auth.schema as auth_schema
import ofscraper.utils.paths.common as common_paths

console = Console()


def read_auth():
    while True:
        with auth_context.auth_context():
            old_auth = helpers.get_auth_dict()
            auth = auth_schema.auth_schema(old_auth)
            if auth_schema.auth_key_missing(old_auth):
                auth = write_auth(auth)
            if auth_schema.auth_key_null(auth):
                auth = make.make_auth(auth)
            request_auth.make_request_auth()
            return auth


def edit_auth():
    while True:
        with auth_context.auth_context():
            auth = helpers.get_auth_dict()
            auth = make.make_auth(auth)
            console.print("Your `auth.json` file has been edited.")
            return auth


def write_auth(auth):
    if isinstance(auth, dict):
        auth = json.dumps(auth, indent=4)
    with open(common_paths.get_auth_file(), "w") as f:
        f.write(auth)
    return helpers.get_auth_dict(auth)
