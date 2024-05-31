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
import logging
import time
from urllib.parse import urlparse

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings


def read_request_auth(refresh=True,forced=False):
    request_auth = {
        "static_param": "",
        "format": "",
        "checksum_indexes": [],
        "checksum_constant": 0,
    }

    # *values, = get_request_auth()
    result = get_request_auth(refresh=refresh,forced=forced)
    if not result:
        raise json.JSONDecodeError("No content")
    (*values,) = result

    request_auth.update(zip(request_auth.keys(), values))
    return request_auth


def get_request_auth(refresh=False,forced=False):
    #curr_auth = cache.get("api_onlyfans_sign")
    # if not (refresh or forced) and curr_auth:
    #     return curr_auth
    logging.getLogger("shared").debug("getting new signature")
    if (settings.get_dynamic_rules()) in {
        "deviint",
        "dv",
        "dev",
    }:

        auth = get_request_auth_deviint()
    elif (settings.get_dynamic_rules()) in {
        "sneaky",
    }:

        auth = get_request_auth_sneaky()
    else:
        auth = get_request_auth_digitalcriminals()
    # if not forced:
    #     cache.set(
    #         "api_onlyfans_sign",
    #         auth,
    #         expire=constants.getattr("HOURLY_EXPIRY") // 4,
    #     )
    return auth


def get_request_auth_deviint():
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
        refresh=False,
    ) as c:
        
        with c.requests(
            constants.getattr("DEVIINT"),
            headers=False,
            cookies=False,
            sign=False,
        ) as r:
            content = r.json_()
            static_param = content["static_param"]
            fmt = f"{content['start']}:{{}}:{{:x}}:{content['end']}"
            checksum_indexes = content["checksum_indexes"]
            checksum_constant = content["checksum_constant"]
            return (static_param, fmt, checksum_indexes, checksum_constant)


def get_request_auth_sneaky():
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
        refresh=False,
    ) as c:
        with c.requests(
            constants.getattr("SNEAKY"),
            headers=False,
            cookies=False,
            sign=False,
        forced=False
        ) as r:
            content = r.json_()
            static_param = content["static_param"]
            fmt = f"{content['prefix']}:{{}}:{{:x}}:{content['suffix']}"
            checksum_indexes = content["checksum_indexes"]
            checksum_constant = content["checksum_constant"]
            return (static_param, fmt, checksum_indexes, checksum_constant)


def get_request_auth_digitalcriminals():
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
        refresh=False,
    ) as c:
        with c.requests(
            constants.getattr("DIGITALCRIMINALS"),
            headers=False,
            cookies=False,
            sign=False,
        ) as r:
            content = r.json_()
            static_param = content["static_param"]
            fmt = content["format"]
            checksum_indexes = content["checksum_indexes"]
            checksum_constant = content["checksum_constant"]
            return (static_param, fmt, checksum_indexes, checksum_constant)


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


def create_sign(link, headers, refresh=False,forced=False):
    """
    credit: DC and hippothon
    """
    content = read_request_auth(refresh=refresh,forced=forced)

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
