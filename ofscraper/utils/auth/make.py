import json
import logging
import re
from contextlib import contextmanager
from urllib.parse import urlparse

from rich.console import Console

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.auth.helpers as helpers
import ofscraper.utils.auth.schema as auth_schema
import ofscraper.utils.paths.common as common_paths

console = Console()


def make_auth(auth=None):
    helpers.authwarning(common_paths.get_auth_file())
    browserSelect = prompts.browser_prompt()

    auth = auth_schema.auth_schema(auth or helpers.get_empty())
    if browserSelect in {"quit", "main"}:
        return browserSelect
    elif browserSelect == "Paste From M-rcus' OnlyFans-Cookie-Helper":
        auth = auth_schema.auth_schema(helpers.cookie_helper_extension())
    elif browserSelect == "Enter Each Field Manually":
        console.print(
            """
You'll need to go to onlyfans.com and retrive/update header information
Go to https://github.com/datawhores/OF-Scraper and find the section named 'Getting Your Auth Info'
You only need to retrive the x-bc header,the user-agent
and cookie information",
 """,
            style="yellow",
        )
        auth.update(prompts.auth_prompt(auth))
    else:
        auth = helpers.browser_cookie_helper(auth, browserSelect)
    for key, item in auth.items():
        newitem = item.strip()
        newitem = re.sub("^ +", "", newitem)
        newitem = re.sub(" +$", "", newitem)
        newitem = re.sub("\n+", "", newitem)
        auth[key] = newitem
    authFile = common_paths.get_auth_file()
    console.print(f"{auth}\nWriting to {authFile}", style="yellow")
    auth = auth_schema.auth_schema(auth)
    with open(authFile, "w") as f:
        f.write(json.dumps(auth, indent=4))
    return auth
