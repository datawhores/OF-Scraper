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

import base64
import hashlib
import json
import logging
import random
import time
from urllib.parse import urlparse

import arrow

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
import  ofscraper.runner.manager as manager



curr_auth = None
last_check = None


def read_request_auth():
    request_auth = {
        "static_param": "",
        "format": "",
        "checksum_indexes": [],
        "checksum_constant": "0",
    }

    # *values, = get_request_auth()
    result = get_request_auth()
    if not result:
        raise json.JSONDecodeError("No content")
    (*values,) = result

    request_auth.update(zip(request_auth.keys(), values))
    return request_auth


def get_request_auth():
    global curr_auth
    global last_check
    if not last_check:
        pass
    elif curr_auth and (
        arrow.now().float_timestamp - last_check.float_timestamp
    ) < constants.getattr("THIRTY_EXPIRY"):
        return curr_auth
    dynamic = settings.get_dynamic_rules()
    auth = None
    if constants.getattr("DYNAMIC_RULE") and dynamic in {"manual"}:
        auth = get_request_auth_dynamic_rule_manual()
    elif constants.getattr("DYNAMIC_GENERIC_URL") and dynamic in {"generic"}:
        auth = get_request_auth_generic()
    elif (dynamic) in {"datawhores"}:
        auth = get_request_auth_datawhores()
    elif (dynamic) in {"xagler"}:
        auth = get_request_auth_xagler()
    elif (dynamic) in {"rafa"}:
        auth = get_request_auth_rafa()
    elif (dynamic) in {"dc", "digital", "digitalcriminal", "digitalcriminals"}:
        auth = get_request_auth_digitalcriminals()
    if auth is None:
        auth = get_request_auth_datawhores()
    cache.set("api_onlyfans_sign", auth, constants.getattr("THIRTY_EXPIRY"))
    curr_auth = auth
    last_check = arrow.now()
    return auth


def get_request_auth_dynamic_rule_manual():
    content = constants.getattr("DYNAMIC_RULE")
    return request_auth_helper_picker(content)


def get_request_auth_generic():
    logging.getLogger("shared").debug("getting new signature with generic")
    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:

        with c.requests(
            constants.getattr("DYNAMIC_GENERIC_URL"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def get_request_auth_deviint():
    logging.getLogger("shared").debug("getting new signature with deviint")

    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:

        with c.requests(
            constants.getattr("DEVIINT"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def get_request_auth_datawhores():
    logging.getLogger("shared").debug("getting new signature with datawhores")

    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:

        with c.requests(
            constants.getattr("DATAWHORES_URL"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def get_request_auth_xagler():
    logging.getLogger("shared").debug("getting new signature with xagler")

    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:

        with c.requests(
            constants.getattr("XAGLER_URL"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def get_request_auth_rafa():
    logging.getLogger("shared").debug("getting new signature with rafa")

    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:

        with c.requests(
            constants.getattr("RAFA_URL"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def get_request_auth_riley():
    logging.getLogger("shared").debug("getting new signature with riley")

    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:

        with c.requests(
            constants.getattr("RILEY_URL"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def get_request_auth_digitalcriminals():
    logging.getLogger("shared").debug("getting new signature with digitalcriminals")

    with manager.Manager.get_session(
        backend="httpx",
        retries=constants.getattr("GIT_NUM_TRIES"),
        wait_min=constants.getattr("GIT_MIN_WAIT"),
        wait_max=constants.getattr("GIT_MAX_WAIT"),
    ) as c:
        with c.requests(
            constants.getattr("DIGITALCRIMINALS"),
        ) as r:
            content = r.json_()
            return request_auth_helper_picker(content)


def request_auth_helper_picker(content):
    if content.get("suffix"):
        return request_auth_helper(content)
    else:
        return request_auth_helper_alt_format(content)


def request_auth_helper_alt_format(content):
    static_param = content["static_param"]
    fmt = content["format"]
    checksum_indexes = content["checksum_indexes"]
    checksum_constant = content["checksum_constant"]
    return (static_param, fmt, checksum_indexes, checksum_constant)


def request_auth_helper(content):
    static_param = content["static_param"]
    fmt = f"{content['prefix']}:{{}}:{{:x}}:{content['suffix']}"
    checksum_indexes = content["checksum_indexes"]
    checksum_constant = content["checksum_constant"]
    return (static_param, fmt, checksum_indexes, checksum_constant)


def make_headers():
    if read_args.retriveArgs().anon:
        return make_anon_headers()
    else:
        return make_login_headers()


def make_anon_headers():
    return {
        "accept": "application/json, text/plain, */*",
        "app-token": constants.getattr("APP_TOKEN"),
        "x-bc": generate_xbc(),
        "referer": "https://onlyfans.com",
        "user-id": "0",
        "user-agent": constants.getattr("ANON_USERAGENT"),
    }


def make_login_headers():
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
    if read_args.retriveArgs().anon:
        return None
    auth = auth_file.read_auth()
    cookies = {}
    cookies.update({"sess": auth["sess"]})
    cookies.update({"auth_id": auth["auth_id"]})
    cookies.update({"auth_uid_": auth["auth_uid"] or auth["auth_id"]})
    return cookies


def get_cookies_str():
    auth = auth_file.read_auth()
    return f"auth_id={auth['auth_id']};sess={auth['sess']};"


def create_sign(link, headers):
    """
    credit: DC and hippothon
    """
    if read_args.retriveArgs().anon:
        return create_anon_sign(link, headers)
    else:
        return create_login_sign(link, headers)


def create_anon_sign(link, headers):
    return create_login_sign(link, headers)


def create_login_sign(link, headers):
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


def generate_xbc():
    """Generates a token based on current time, random numbers, and user agent.

    Returns:
      A string containing the generated token.
    """
    parts = [
        int(time.time() * 1000),  # Milliseconds since epoch
        int(1e12 * random.random()),
        int(1e12 * random.random()),
        # Assuming you have a way to get the user agent string
        # Replace this with your logic to retrieve the user agent
        constants.getattr("ANON_USERAGENT"),
    ]
    msg = ".".join(
        [base64.b64encode(str(p).encode("utf-8")).decode("utf-8") for p in parts]
    )
    token = hashlib.sha1(msg.encode("utf-8"), usedforsecurity=False).hexdigest()
    return token
