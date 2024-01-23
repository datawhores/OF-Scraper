r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import sys

from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from InquirerPy.validator import EmptyInputValidator
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses

console = Console()


def auth_prompt(auth) -> dict:
    answers = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "sess",
                "message": "Enter your sess cookie:",
                "default": auth["sess"],
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
            {
                "type": "input",
                "name": "auth_id",
                "message": "Enter your auth_id cookie:",
                "default": auth["auth_id"],
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
            {
                "type": "input",
                "name": "auth_uid_",
                "message": "Enter your auth_uid cookie (can be left blank if you don't use 2FA):",
                "default": auth["auth_uid_"],
                "multiline": True,
            },
            {
                "type": "input",
                "name": "user_agent",
                "message": "Enter your `user agent`:",
                "default": auth["user_agent"],
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
            {
                "type": "input",
                "name": "x-bc",
                "message": "Enter your `x-bc` token:",
                "default": auth["x-bc"],
                "validate": EmptyInputValidator(),
                "multiline": True,
            },
        ]
    )

    return answers


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


def browser_prompt() -> str:
    pythonver = float(f"{sys.version_info[0]}.{sys.version_info[1]}")
    name = "browser"
    answer = None

    if pythonver < 3.9 or pythonver >= 3.11:
        msg = "Select how to retrive auth information"
        console.print(
            "\nNote: Browser Extractions only works with default browser profile\n\n"
        )
        answer = promptClasses.batchConverter(
            *[
                {
                    "type": "list",
                    "message": msg,
                    "name": name,
                    "choices": [
                        "Enter Each Field Manually",
                        "Paste From M-rcus' OnlyFans-Cookie-Helper",
                        Separator(line="-----------\nBrowser Extractions"),
                        "Chrome",
                        "Chromium",
                        "Firefox",
                        "Opera",
                        "Opera GX",
                        "Edge",
                        "Chromium",
                        "Brave",
                        "Vivaldi",
                        "Safari",
                    ],
                    "default": "Enter Each Field Manually",
                }
            ]
        )

    else:
        console.print(
            "\nNote:To enable automatic extraction install ofscraper with python 3.9 or 3.10\n\n"
        )
        msg = "Select how to retrive auth information"
        answer = promptClasses.batchConverter(
            *[
                {
                    "type": "list",
                    "message": msg,
                    "choices": [
                        "Enter Each Field Manually",
                        "Paste From Cookie Helper",
                    ],
                    "default": "Enter Each Field Manually",
                }
            ]
        )

    return answer[name]


def user_agent_prompt(current):
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": "Enter User_Agent from browser",
                "default": current,
                "validate": EmptyInputValidator(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
            }
        ]
    )
    return questions[name]


def xbc_prompt():
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": "Enter x-bc request header",
                "instruction": f"\nGo to browser network tools to view\nFor more instructions visit https://github.com/datawhores/ofscraper\n\n",
                "validate": EmptyInputValidator(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
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
    return questions[name]


def reset_auth_prompt() -> bool:
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "How do you want to fix this issue",
                "choices": [
                    Choice("Reset Default", "Reset Default"),
                    Choice("Manually Edit Auth Config", "Manually Edit Auth Config"),
                ],
            }
        ]
    )
    return questions[name]
