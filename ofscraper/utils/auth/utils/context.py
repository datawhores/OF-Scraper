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
from contextlib import contextmanager

from rich.console import Console

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.auth.make as make
import ofscraper.utils.auth.utils.dict as auth_dict
import ofscraper.utils.paths.common as common_paths

console = Console()
log = logging.getLogger("shared")


@contextmanager
def auth_context():
    try:
        yield
    except FileNotFoundError:
        console.print("You don't seem to have an `auth.json` file")
        make.make_auth()
    except json.JSONDecodeError as e:
        while True:
            try:
                print("Your auth.json has a syntax error")
                print(f"{e}\n\n")
                auth_prompt = prompts.reset_auth_prompt()
                if auth_prompt == "manual":
                    authStr = auth_dict.get_auth_string()
                    with open(common_paths.get_auth_file(), "w") as f:
                        f.write(prompts.manual_auth_prompt(authStr))
                elif auth_prompt == "reset":
                    with open(common_paths.get_auth_file(), "w") as f:
                        f.write(json.dumps(auth_dict.get_empty()))
                auth_dict.get_auth_dict()
                break
            except Exception:
                continue
