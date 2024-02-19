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

import browser_cookie3
import requests
from rich.console import Console

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.paths.common as common_paths

console = Console()
log = logging.getLogger("shared")


def get_auth_dict(authStr=None):
    auth = json.loads(authStr or get_auth_string())
    if "auth" in auth:
        return auth.get("auth")
    return auth


def get_auth_string():
    authFile = common_paths.get_auth_file()
    with open(authFile, "r") as f:
        authText = f.read()
    return authText


def get_empty():
    return {
        "sess": "",
        "auth_id": "",
        "auth_uid": "",
        "user_agent": "",
        "x-bc": "",
    }


def authwarning(authFile):
    console.print(
        "[bold yellow]For an example of how your auth file should look see \
            \n [bold blue]https://of-scraper.gitbook.io/of-scraper/auth#example[/bold blue][/bold yellow]"
    )
    console.print(
        f"[bold yellow]If you still can't authenticate after editing from script consider manually edit the file at\n[bold blue]{authFile}[/bold blue][/bold yellow]"
    )


def browser_cookie_helper(auth, browserSelect):
    temp = requests.utils.dict_from_cookiejar(
        getattr(browser_cookie3, browserSelect.lower())(domain_name="onlyfans")
    )
    for key in ["sess", "auth_id", "auth_uid_"]:
        auth[key] = auth[key] or temp.get(key, "")
    console.print(
        "You'll need to go to onlyfans.com and retrive/update header information\nGo to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'\nCookie information has been retived automatically\nSo You only need to retrive the x-bc header and the user-agent",
        style="yellow",
    )
    auth["x-bc"] = prompts.xbc_prompt(auth.get("x-bc"))
    auth["user_agent"] = prompts.user_agent_prompt(auth.get("user_agent"))


def cookie_helper_extension():
    return prompts.auth_full_paste()
