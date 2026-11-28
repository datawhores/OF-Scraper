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
import logging

import ofscraper.utils.encoding as encoding
import ofscraper.utils.paths.common as common_paths

log = logging.getLogger("shared")


def get_auth_dict(authStr=None):
    auth = json.loads(authStr or get_auth_string())
    if "auth" in auth:
        return auth.get("auth")
    return auth


def get_auth_string():
    authFile = common_paths.get_auth_file()
    return encoding.read_text_file(authFile)


def get_empty():
    return {
        "sess": "",
        "auth_id": "",
        "auth_uid": "",
        "user_agent": "",
        "x-bc": "",
    }
