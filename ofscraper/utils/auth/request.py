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

import hashlib
import json
import time
from contextlib import contextmanager
from urllib.parse import urlparse

from tenacity import (
    Retrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_fixed,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.profiles.data as profiles_data
import ofscraper.utils.settings as settings


def make_request_auth():
    request_auth = {
        "static_param": "",
        "format": "",
        "checksum_indexes": [],
        "checksum_constant": 0,
    }

    # *values, = get_request_auth()
    result = get_request_auth()
    if result:
        (*values,) = result

        request_auth.update(zip(request_auth.keys(), values))

        profile = profiles_data.get_active_profile()

        p = common_paths.get_config_home() / profile
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)

        with open(p / constants.getattr("requestAuth"), "w") as f:
            f.write(json.dumps(request_auth, indent=4))


def get_request_auth():
    if (settings.get_dynamic_rules()) in {
        "deviint",
        "dv",
        "dev",
    }:
        return get_request_auth_deviint()
    else:
        return get_request_digitalcriminals()


def get_request_auth_deviint():
    with sessionbuilder.sessionBuilder(
        backend="httpx", set_header=False, set_cookies=False, set_sign=False
    ) as c:
        for _ in Retrying(
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
            wait=wait_fixed(8),
        ):
            with _:
                with c.requests(constants.getattr("DEVIINT"))() as r:
                    if r.ok:
                        content = r.json_()
                        static_param = content["static_param"]
                        fmt = f"{content['start']}:{{}}:{{:x}}:{content['end']}"
                        checksum_indexes = content["checksum_indexes"]
                        checksum_constant = content["checksum_constant"]
                        return (static_param, fmt, checksum_indexes, checksum_constant)
                    else:
                        r.raise_for_status()


def get_request_digitalcriminals():
    with sessionbuilder.sessionBuilder(
        backend="httpx", set_header=False, set_cookies=False, set_sign=False
    ) as c:
        for _ in Retrying(
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
            wait=wait_fixed(8),
        ):
            with _:
                with c.requests(constants.getattr("DIGITALCRIMINALS"))() as r:
                    if r.ok:
                        content = r.json_()
                        static_param = content["static_param"]
                        fmt = content["format"]
                        checksum_indexes = content["checksum_indexes"]
                        checksum_constant = content["checksum_constant"]
                        return (static_param, fmt, checksum_indexes, checksum_constant)
                    else:
                        r.raise_for_status()


def make_headers():
    auth = auth_file.read_auth()
    headers = {
        "accept": "application/json, text/plain, */*",
        "app-token": constants.getattr("APP_TOKEN"),
        "user-id": auth["auth_id"],
        "x-bc": auth["x-bc"],
        "referer": "https://onlyfans.com",
        "user-agent": auth["user_agent"],
    }
    return headers


def add_cookies():
    auth = auth_file.read_auth()
    cookies = {}
    cookies.update({"sess": auth["sess"]})
    cookies.update({"auth_id": auth["auth_id"]})
    cookies.update({"auth_uid_": auth["auth_uid"] or auth["auth_id"]})
    return cookies


def get_cookies():
    auth = auth_file.read_auth()
    return f"auth_id={auth['auth_id']};sess={auth['sess']};"


def create_sign(link, headers):
    """
    credit: DC and hippothon
    """
    content = read_request_auth()

    time2 = str(round(time.time() * 1000))

    path = urlparse(link).path
    query = urlparse(link).query
    path = path if not query else f"{path}?{query}"

    static_param = content["static_param"]

    a = [static_param, time2, path, headers["user-id"]]
    msg = "\n".join(a)

    message = msg.encode("utf-8")
    hash_object = hashlib.sha1(message, usedforsecurity=False)
    sha_1_sign = hash_object.hexdigest()
    sha_1_b = sha_1_sign.encode("ascii")

    checksum_indexes = content["checksum_indexes"]
    checksum_constant = content["checksum_constant"]
    checksum = sum(sha_1_b[i] for i in checksum_indexes) + checksum_constant

    final_sign = content["format"].format(sha_1_sign, abs(checksum))

    headers.update({"sign": final_sign, "time": time2})
    return headers


def read_request_auth() -> dict:
    profile = profiles_data.get_active_profile()

    p = common_paths.get_config_home() / profile / constants.getattr("requestAuth")
    with open(p, "r") as f:
        content = json.load(f)
    return content
