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
import re

from rich.console import Console

import ofscraper.utils.auth.make as make
import ofscraper.utils.auth.schema as auth_schema
import ofscraper.utils.auth.utils.error as auth_error
import ofscraper.utils.auth.utils.dict as auth_dict
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.logs.utils.sensitive as sensitive
console = Console()


def read_auth():
    """
    Reads and validates the auth file, handling errors interactively.
    Returns the auth dictionary
    """
    while True:
        try:
            # Attempt to get the auth data
            old_auth = auth_dict.get_auth_dict()
            auth = auth_schema.auth_schema(old_auth)

            # Perform normal logic checks
            if auth_schema.auth_key_missing(old_auth):
                auth = write_auth(auth)
            if auth_schema.auth_key_null(auth):
                auth,_ = make.make_auth(auth)
            
            # If all checks pass, break the loop and return the auth data
            break

        except (FileNotFoundError, json.JSONDecodeError) as e:
            result = auth_error.handle_auth_errors(e)
            if result =="quit":
                logging.getLogger("shared").info("unable to read auth file")
                quit()
    hide_secrets(auth)
    return auth


MIN_SECRET_LENGTH = 8


def hide_secrets(auth):
    """Mask the session cookie wherever it appears in a log line.

    Request headers are logged when a request fails, and the cookie header
    holds ``sess=<value>``. Registering the value itself covers every form it
    is logged in (cookie header, dict repr, JSON).
    """
    sess = auth.get("sess") if isinstance(auth, dict) else None
    # a real session value is long; a stray short one (e.g. a placeholder)
    # would mask ordinary words in every log line
    if sess and len(str(sess)) >= MIN_SECRET_LENGTH:
        sensitive.add_sensitive_pattern(re.compile(re.escape(str(sess))), "{sess}")


def edit_auth():
    """
    Opens the auth editing menu, handling errors interactively.
    Returns the new auth dictionary or a command string ('quit', 'main').
    """
    while True:
        try:
            auth_dict.get_auth_dict()           
            break
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Delegate error handling
            result = auth_error.handle_auth_errors(e,include_main_menu=True)
            if result in {"quit", "main"}:
                return result
    
    current_auth = auth_dict.get_auth_dict()
    new_auth,result = make.make_auth(current_auth, include_main_menu=True)
    
    # Check if the user quit from the edit menu itself
    if result in {"quit", "main"}:
        return result

    console.print("Your `auth.json` file has been edited.")
    return new_auth


def write_auth(auth):
    if isinstance(auth, dict):
        auth = json.dumps(auth, indent=4)
    with open(common_paths.get_auth_file(), "w") as f:
        f.write(auth)
    return auth_dict.get_auth_dict(auth)
