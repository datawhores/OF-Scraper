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

import sys
from functools import partial

from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from InquirerPy.validator import EmptyInputValidator
from rich.console import Console

import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
from ofscraper.utils.auth.utils.warning.print import print_auth_warning

console = Console()


def auth_prompt(auth) -> dict:
    answers = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "sess",
                "message": "Enter your sess cookie:",
                "default": auth["sess"] or "",
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
            {
                "type": "input",
                "name": "auth_id",
                "message": "Enter your auth_id cookie:",
                "default": auth["auth_id"] or "",
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
            {
                "type": "input",
                "name": "auth_uid",
                "message": "Enter your auth_uid cookie (can be left blank if you don't use 2FA):",
                "default": auth["auth_uid"] or "",
                "multiline": True,
            },
            {
                "type": "input",
                "name": "user_agent",
                "message": "Enter your `user agent`:",
                "default": auth["user_agent"] or "",
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
            {
                "type": "input",
                "name": "x-bc",
                "message": "Enter your `x-bc` token:",
                "default": auth["x-bc"] or "",
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
        ]
    )

    return answers


def manual_auth_prompt(authText) -> str:
    name = "input"

    questions = promptClasses.batchConverter(
        *[
            {
                "name": name,
                "type": "input",
                "multiline": True,
                "default": authText,
                "message": "Edit auth text\n===========\n",
                "long_message": prompt_strings.AUTH_MULTI,
                "validate": EmptyInputValidator(),
            }
        ]
    )

    return questions[name]


def ask_make_auth_prompt() -> bool:
    name = "make_auth"

    questions = promptClasses.batchConverter(
        *[
            {
                "type": "confirm",
                "name": name,
                "message": "You don't seem to have an `auth.json` file. Would you like to make one?",
            }
        ]
    )

    return questions[name]


def prompt_for_browser_auth(include_main_menu: bool = True) -> str:
    """
    Prompts the user for an authentication method.

    This function is completely self-contained and does not rely on
    any module-level constants.

    Args:
        include_main_menu (bool): If True, includes an option to return to the main menu.

    Returns:
        str: The user's selected choice.
   
    """
    extraction_enabled_note = "\nNote: Browser Extractions only work with default browser profile\n\nHint: Select 'Enter Each Field Manually' to edit your current config\n"
    extraction_disabled_note = "\nNote: To enable automatic extraction, install with Python 3.9 or greater\n\nHint: Select 'Enter Each Field Manually' to edit your current config\n"
    msg = "Auth Menu: Select how to retrieve auth information"

    supported_browsers = [
        "Chrome", "Chromium", "Firefox", "Opera", "Opera GX",
        "Edge", "Brave", "Vivaldi", "Safari",
    ]

    main_menu_choice = Choice(name="Go to Main Menu", value="main")
    quit_choice = Choice(name="Quit", value="quit")

    # --- Function Logic ---
    name = "browser"
    choices = [
        "Enter Each Field Manually",
        "Paste From M-rcus' OnlyFans-Cookie-Helper",
    ]

    if sys.version_info >= (3, 9):
        print(extraction_enabled_note)
        choices.extend([
            Separator("-----------\nBrowser Extractions"),
            *supported_browsers,
        ])
    else:
        print(extraction_disabled_note)

    choices.append(Separator("-----------"))
    if include_main_menu:
        choices.append(main_menu_choice)
    choices.append(quit_choice)
    answer = promptClasses.batchConverter(
            *[
                {
                    "type": "list",
                    "message": msg,
                    "name": name,
                    "choices": choices,
                    "default": "Enter Each Field Manually",
                }
            ]
        )
    
    if not answer:
        return "quit"
    
    return answer[name]


def user_agent_prompt(current):
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": "Enter User_Agent from browser",
                "default": current or "",
                "validate": EmptyInputValidator(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
            }
        ]
    )
    return questions[name]


def xbc_prompt(xbc):
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": "Enter x-bc request header",
                "instruction": "\nGo to browser network tools to view\nFor more instructions visit https://github.com/datawhores/ofscraper\n\n",
                "validate": EmptyInputValidator(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
                "default": xbc or "",
            }
        ]
    )
    return questions[name]


def auth_full_paste():
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": "Paste Text from Extension",
                "validate": prompt_validators.jsonValidator(),
                "filter": prompt_validators.jsonloader,
                "multiline": True,
                "instruction": """
Cookie Helper Repo:https://github.com/M-rcus/OnlyFans-Cookie-Helper
""",
            }
        ]
    )
    return questions[name]["auth"]


def reset_auth_prompt(include_main_menu=False) -> bool:
    name = "input"
    choices=[
                    Choice("reset", "Reset Default"),
                    Choice("manual", "Fix Through Script"),
                    Choice("again", "File was fixed manually"),
                    Choice("quit", "Quit"),

                ]
    if include_main_menu:
        choices.append(                    Choice("main", "Main Menu"),
)
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "How do you want to fix this issue",
                "choices": choices,
            }
        ]
    )
    return questions[name]


def check_auth_prompt(auth) -> bool:

    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Is the auth information correct",
                "call": partial(print_auth_warning, auth),
                "choices": [
                    Choice(True, "Yes"),
                    Choice(False, "No"),
                ],
            }
        ]
    )
    return questions[name]
