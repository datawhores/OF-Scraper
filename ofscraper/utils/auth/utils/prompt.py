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

import logging

import browser_cookie3
from rich.console import Console

import ofscraper.prompts.prompts as prompts

console = Console()
log = logging.getLogger("shared")


def browser_cookie_helper(auth, browserSelect):
    jar = getattr(browser_cookie3, browserSelect.lower())(domain_name="onlyfans")
    temp = {cookie.name: cookie.value for cookie in jar}
    for key in ["sess", "auth_id", "auth_uid_"]:
        auth[key] = auth[key] or temp.get(key, "")
    console.print(
        "You'll need to go to onlyfans.com and retrive/update header information\nGo to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'\nCookie information has been retived automatically\nSo You only need to retrive the x-bc header and the user-agent",
        style="yellow",
    )
    auth["x-bc"] = prompts.xbc_prompt(auth.get("x-bc"))
    auth["user_agent"] = prompts.user_agent_prompt(auth.get("user_agent"))


def cookie_helper_extension():
    result=prompts.auth_full_paste()
    return result.get("auth") or result
