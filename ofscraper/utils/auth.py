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
import re
import time
from urllib.parse import urlparse

import browser_cookie3
import requests
from rich.console import Console
from tenacity import (
    Retrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_fixed,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.profiles.data as profiles_data

console = Console()
log = logging.getLogger("shared")


def read_auth():
    authFile = common_paths.get_auth_file()
    while True:
        try:
            with open(authFile, "r") as f:
                authText = f.read()
                auth = json.loads(authText)
                nested_auth = auth["auth"]
                for key in nested_auth.keys():
                    if key == "auth_uid_":
                        continue
                    elif nested_auth[key] == None or nested_auth[key] == "":
                        console.print("Auth Value not set retriving missing values")
                        make_auth()
                        break
                    value = str(nested_auth[key]).strip()
                    re.sub("^ +", "", value)
                    value = re.sub(" +$", "", value)
                    value = re.sub("\n+", "", value)
                    nested_auth[key] = value
            break
        except FileNotFoundError:
            console.print("You don't seem to have an `auth.json` file")
            make_auth()
        except json.JSONDecodeError as e:
            print("Your auth.json has a syntax error")
            print(f"{e}\n\n")
            auth_prompt = prompts.reset_auth_prompt()
            if auth_prompt == "manual":
                with open(authFile, "w") as f:
                    f.write(prompts.manual_auth_prompt(authText))
            elif auth_prompt == "reset":
                with open(authFile, "w") as f:
                    f.write(json.dumps(get_empty()))

    make_request_auth()
    return auth


def get_empty():
    return {
        "auth": {
            "sess": "",
            "auth_id": "",
            "auth_uid_": "",
            "user_agent": "",
            "x-bc": "",
        }
    }


def edit_auth():
    authFile = common_paths.get_auth_file()
    log.info(f"Auth Path {authFile}")
    try:
        with open(authFile, "r") as f:
            authText = f.read()
            auth = json.loads(authText)
        return make_auth(auth)

        console.print("Your `auth.json` file has been edited.")
    except FileNotFoundError:
        if prompts.ask_make_auth_prompt():
            return make_auth()
    except json.JSONDecodeError as e:
        while True:
            try:
                print("Your auth.json has a syntax error")
                auth_prompt = prompts.reset_auth_prompt()
                if auth_prompt == "reset":
                    return make_auth()
                elif auth_prompt == "manual":
                    with open(authFile, "w") as f:
                        f.write(prompts.manual_auth_prompt(authText))

                with open(authFile, "r") as f:
                    authText = f.read()
                    auth = json.loads(authText)
                break
            except Exception:
                continue


def authwarning(authFile):
    console.print(
        "[bold yellow]For an example of how your auth file should look see \
            \n [bold blue]https://of-scraper.gitbook.io/of-scraper/auth#example[/bold blue][/bold yellow]"
    )
    console.print(
        f"[bold yellow]If you still can't authenticate after editing from script consider manually edit the file at\n[bold blue]{authFile}[/bold blue][/bold yellow]"
    )


def make_auth(auth=None):
    authFile = common_paths.get_auth_file()
    authwarning(authFile)
    defaultAuth = get_empty()

    browserSelect = prompts.browser_prompt()

    auth = auth or defaultAuth
    if browserSelect in {"quit", "main"}:
        return browserSelect
    elif (
        browserSelect != "Enter Each Field Manually"
        and browserSelect != "Paste From M-rcus' OnlyFans-Cookie-Helper"
    ):
        temp = requests.utils.dict_from_cookiejar(
            getattr(browser_cookie3, browserSelect.lower())(domain_name="onlyfans")
        )
        auth = auth or defaultAuth
        for key in ["sess", "auth_id", "auth_uid_"]:
            auth["auth"][key] = temp.get(key, "")
        console.print(
            "You'll need to go to onlyfans.com and retrive header information\nGo to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'\nCookie information has been retived automatically\nSo You only need to retrive the x-bc header and the user-agent",
            style="yellow",
        )
        if not auth["auth"].get("x-bc"):
            auth["auth"]["x-bc"] = prompts.xbc_prompt()
        auth["auth"]["user_agent"] = prompts.user_agent_prompt(
            auth["auth"].get("user_agent") or ""
        )

    elif browserSelect == "Paste From M-rcus' OnlyFans-Cookie-Helper":
        auth = prompts.auth_full_paste()
        for key in ["username", "support_2fa", "active", "email", "password", "hashed"]:
            auth["auth"].pop(key)
        auth["auth"]["x-bc"] = auth["auth"].pop("x_bc").strip()
        tempCookie = auth["auth"].pop("cookie")
        for ele in tempCookie.split(";"):
            if ele.find("auth_id") != -1:
                auth["auth"]["auth_id"] = ele.replace("auth_id=", "")
            elif ele.find("sess") != -1:
                auth["auth"]["sess"] = ele.replace("sess=", "")
            elif ele.find("auth_uid") != -1:
                auth["auth"]["auth_uid_"] = ele.replace("auth_uid_", "").replace(
                    "=", ""
                )

    else:
        console.print(
            "You'll need to go to onlyfans.com and retrive header information\nGo to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'\nYou only need to retrive the x-bc header,the user-agent, and cookie information",
            style="yellow",
        )
        auth["auth"].update(prompts.auth_prompt(auth["auth"]))
    for key, item in auth["auth"].items():
        newitem = item.strip()
        newitem = re.sub("^ +", "", newitem)
        newitem = re.sub(" +$", "", newitem)
        newitem = re.sub("\n+", "", newitem)
        auth["auth"][key] = newitem
    console.print(f"{auth}\nWriting to {authFile}", style="yellow")
    with open(authFile, "w") as f:
        f.write(json.dumps(auth, indent=4))


def make_headers(auth):
    headers = {
        "accept": "application/json, text/plain, */*",
        "app-token": constants.getattr("APP_TOKEN"),
        "user-id": auth["auth"]["auth_id"],
        "x-bc": auth["auth"]["x-bc"],
        "referer": "https://onlyfans.com",
        "user-agent": auth["auth"]["user_agent"],
    }
    return headers


def add_cookies():
    authFile = common_paths.get_auth_file()
    with open(authFile, "r") as f:
        auth = json.load(f)

    cookies = {}
    cookies.update({"sess": auth["auth"]["sess"]})
    cookies.update({"auth_id": auth["auth"]["auth_id"]})
    cookies.update({"auth_uid_": auth["auth"]["auth_uid_"] or auth["auth"]["auth_id"]})
    return cookies


def get_cookies():
    authFile = common_paths.get_auth_file()

    with open(authFile, "r") as f:
        auth = json.load(f)
    return f"auth_id={auth['auth']['auth_id']};sess={auth['auth']['sess']};"


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
    if (read_args.retriveArgs().dynamic_rules or data.get_dynamic() or "deviint") in {
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
