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

from rich.console import Console

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.auth.make as make
import ofscraper.utils.auth.utils.dict as auth_dict
import ofscraper.utils.paths.common as common_paths

console = Console()
log = logging.getLogger("shared")


def handle_auth_errors(e: Exception,include_main_menu:bool=False) -> str | None:
    """
    Handles auth file errors by prompting the user.

    Args:
        e (Exception): The exception caught (FileNotFoundError or JSONDecodeError).
        include_main_menu (Bool): add the main_menu to choices in user prompt

    Returns:
        str | None: "quit" or "main" if the user chooses to exit, 
                    or None if the user fixes the issue and the operation should be retried.
    """
    if isinstance(e, FileNotFoundError):
        console.print("You don't seem to have an `auth.json` file. Creating one for you.")
        # make_auth will guide the user. It returns "quit" or "main" if the user backs out.
        result = make.make_auth(include_main_menu=include_main_menu)
        if result in {"quit", "main"}:
            return result

    elif isinstance(e, json.JSONDecodeError):
        console.print(f"[bold red]Error:[/bold red] Your 'auth.json' file has a syntax error at line {e.lineno}, column {e.colno}.")
        while True:
            try:
                # This prompt should be defined in your prompts module
                auth_prompt = prompts.reset_auth_prompt(include_main_menu=include_main_menu)   
                if auth_prompt == "manual":
                    # Let the user manually fix the file content
                    authStr = auth_dict.get_auth_string()
                    with open(common_paths.get_auth_file(), "w") as f:
                        f.write(prompts.manual_auth_prompt(authStr))
                elif auth_prompt == "reset":
                    # Overwrite with a blank, valid JSON
                    with open(common_paths.get_auth_file(), "w") as f:
                        f.write(json.dumps(auth_dict.get_empty(), indent=4))
                    console.print("`auth.json` has been reset.")
                elif auth_prompt in {"quit", "main"}:
                    return auth_prompt

                # After fixing, check if the file is now valid JSON before breaking the loop
                auth_dict.get_auth_dict() 
                console.print("`auth.json` has been fixed.")
                break
            except Exception as new_e:
                console.print(f"An error occurred while trying to fix the file: {new_e}")
                # Loop continues to give user another chance
                continue
    
    # Return None to signal that the error was handled and the calling function should retry
    return None