r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import copy
import json
import logging
import os
import re
import sys

from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from InquirerPy.validator import EmptyInputValidator, PathValidator
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.filters.models.selector as userselector
import ofscraper.prompts.model_helpers as modelHelpers
import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as data
import ofscraper.utils.config.schema as schema
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths

console = Console()


def main_prompt() -> int:
    main_prompt_choices = [*constants.getattr("mainPromptChoices")]
    main_prompt_choices.insert(3, Separator())
    main_prompt_choices.insert(8, Separator())
    answer = promptClasses.getChecklistSelection(
        message="What would you like to do?", choices=[*main_prompt_choices]
    )
    return constants.getattr("mainPromptChoices")[answer]


def action_prompt() -> int:
    action_prompt_choices = [*constants.getattr("ActionPromptChoices")]
    action_prompt_choices.insert(3, Separator())
    action_prompt_choices.insert(6, Separator())
    action_prompt_choices.insert(9, Separator())
    answer = promptClasses.getChecklistSelection(
        message="What action(s) would you like to take?",
        choices=[*action_prompt_choices],
    )
    args = read_args.retriveArgs()
    action = constants.getattr("ActionPromptChoices")[answer]
    if isinstance(action, str):
        return action
    args.action = action
    write_args.setArgs(args)


def areas_prompt() -> list:
    args = read_args.retriveArgs()
    name = "value"
    message = (
        "Which area(s) would you do you want to download and like"
        if "like" in args.action and len(args.like_area) == 0
        else "Which area(s) would you want to download and unlike"
        if "unike" in args.action and len(args.like_area) == 0
        else "Which area(s) would you like to download"
    )
    long_instruction = (
        "Hint: Since Have Like or Unlike Set\nYou must select one or more of Timeline,Pinned,Archived, or Label "
        if ("like" or "unlike") in args.action and len(args.like_area) == 0
        else ""
    )
    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": message,
                "long_instruction": long_instruction,
                "validate": prompt_validators.MultiValidator(
                    prompt_validators.emptyListValidator(),
                    prompt_validators.like_area_validator_posts(),
                ),
                "choices": [
                    Choice("Profile"),
                    Choice("Timeline"),
                    Choice("Pinned"),
                    Choice("Archived"),
                    Choice("Highlights"),
                    Choice("Stories"),
                    Choice("Messages"),
                    Choice("Purchased"),
                    Choice("Labels"),
                ],
            }
        ]
    )
    return answers[name]


def like_areas_prompt(like=True) -> list:
    name = "areas"

    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": f"Which area(s) would you to perform {'like' if like else 'unlike'} actions on",
                "validate": prompt_validators.emptyListValidator(),
                "choices": [
                    Choice("Timeline"),
                    Choice("Pinned"),
                    Choice("Archived"),
                    Choice("Labels"),
                ],
            }
        ]
    )
    return answers[name]


def download_areas_prompt() -> list:
    name = "areas"

    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": f"Which area(s) would you to perform download actions on",
                "validate": prompt_validators.emptyListValidator(),
                "choices": [
                    Choice("Profile"),
                    Choice("Timeline"),
                    Choice("Pinned"),
                    Choice("Archived"),
                    Choice("Highlights"),
                    Choice("Stories"),
                    Choice("Messages"),
                    Choice("Purchased"),
                    Choice("Labels"),
                ],
            }
        ]
    )
    return answers[name]


def scrape_paid_prompt():
    name = "value"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Scrape entire paid page\n\n[Warning: initial Scan can be slow]\n[Caution: You should not need this unless your're looking to scrape paid content from a deleted/banned model]",
                "choices": [Choice(True, "True"), Choice(False, "False", enabled=True)],
                "long_instruction": prompt_strings.SCRAPE_PAID,
                "default": False,
            },
        ]
    )

    return answer[name]


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
                "message": "Enter your auth_uid cookie (leave blank if you don't use 2FA):",
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


def profiles_prompt() -> int:
    name = "profile"

    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Select one of the following:",
                "choices": [*constants.getattr("profilesPromptChoices")],
            }
        ]
    )

    return constants.getattr("profilesPromptChoices").get(questions[name])


def edit_profiles_prompt(profiles) -> str:
    name = "edit"

    profile_names = [profile.stem for profile in profiles]

    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Which profile would you like to edit?",
                "choices": [*profile_names],
            }
        ]
    )

    return questions[name]


def new_name_edit_profiles_prompt(old_profile_name) -> str:
    name = "new_name"

    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": f"What would you like to rename {old_profile_name} to?",
                "validate": prompt_validators.MultiValidator(
                    EmptyInputValidator(), prompt_validators.currentProfilesValidator()
                ),
            }
        ]
    )

    return answer[name]


def create_profiles_prompt() -> str:
    name = "create"

    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": name,
                "message": """
What would you like to name your new profile?
only letters, numbers, and underscores are allowed
""",
                "validate": prompt_validators.MultiValidator(
                    prompt_validators.namevalitator(),
                    prompt_validators.currentProfilesCreationValidator(),
                ),
            }
        ]
    )

    return answer[name]


def get_profile_prompt(profiles: list) -> str:
    name = "get_profile"

    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Select Profile",
                "choices": profiles,
                "validate": prompt_validators.MultiValidator(
                    prompt_validators.emptyListValidator()
                ),
            }
        ]
    )
    profile = answer[name]
    return profile


def config_prompt_advanced() -> dict:
    custom = {}
    threads = promptClasses.batchConverter(
        *[
            {
                "type": "number",
                "name": "threads",
                "message": "Number of Download processes/threads: ",
                "min_allowed": 0,
                "max_allowed": os.cpu_count() - 1,
                "validate": EmptyInputValidator(),
                "long_instruction": f"Value can be 1-{os.cpu_count()-1}",
                "default": data.get_threads(),
            },
        ]
    )

    custom.update(threads)
    max_allowed = cache.get("speed_download")
    if not cache.get("speed_download") or promptClasses.getChecklistSelection(
        choices=[Choice(True, "Yes"), Choice(False, "No")],
        message="Re-run speedtest",
        long_instruction="Download Sems max value is based on calculated speed",
        default=False,
    ):
        speed = get_speed(threads)
        max_allowed = speed
        cache.set("speed_download", speed)
        cache.close()
    new_settings = promptClasses.batchConverter(
        *[
            {
                "type": "number",
                "name": "download-sem",
                "message": "Number of semaphores per thread: ",
                "min_allowed": 1,
                "max_allowed": max_allowed,
                "validate": EmptyInputValidator(),
                "long_instruction": f"Value can be 1-{max_allowed}",
                "default": data.get_download_semaphores(),
            },
            {
                "type": "list",
                "name": "avatars",
                "message": "Show Avatars in Log",
                "default": data.get_avatar(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
            {
                "type": "list",
                "name": "dynamic-mode-default",
                "message": "What would you like to use for dynamic rules\nhttps://grantjenks.com/docs/diskcache/tutorial.html#caveats",
                "default": data.get_dynamic(),
                "choices": ["deviint", "digitalcriminals"],
            },
            {
                "type": "list",
                "name": "cache-mode",
                "message": "sqlite should be fine unless your using a network drive\nSee",
                "default": data.cache_mode_helper(),
                "choices": ["sqlite", "json", "disabled"],
            },
            {
                "type": "list",
                "name": "key-mode-default",
                "message": "Make selection for how to retrive long_message",
                "default": data.get_key_mode(),
                "choices": constants.getattr("KEY_OPTIONS"),
            },
            {
                "type": "input",
                "name": "keydb_api",
                "message": "keydb api key:\n",
                "long_instruction": "Required if your using keydb for key-mode",
                "default": data.get_keydb_api() or "",
            },
            {
                "type": "filepath",
                "name": "client-id",
                "message": "Enter path to client id file",
                "default": data.get_client_id() or "",
            },
            {
                "type": "filepath",
                "name": "private-key",
                "message": "Enter path to private-key",
                "default": data.get_private_key() or "",
            },
            {
                "type": "list",
                "name": "backend",
                "choices": [Choice("aio", "aiohttp"), Choice("httpx", "httpx")],
                "message": "Select Which Backend you want:\n",
                "default": data.get_backend() or "",
            },
            # value because of legacy config values
            {
                "type": "list",
                "name": "partfileclean",
                "message": "Enable auto file resume",
                "long_instruction": "Enable this if you don't want to auto resume files, and want .part files auto cleaned",
                "default": data.get_part_file_clean(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
            {
                "type": "input",
                "name": "custom",
                "message": "edit custom value:\n",
                "long_instruction": "This is a helper value for remapping placeholder values",
                "default": json.dumps(custom.get_custom())
                if not isinstance(custom.get_custom(), str)
                else custom.get_custom() or "",
            },
            {
                "type": "list",
                "name": "downloadbars",
                "message": "show download progress bars\nThis can have a negative effect on performance with lower threads",
                "default": data.get_show_downloadprogress(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
            {
                "type": "list",
                "name": "code-execution",
                "message": "Enable Code Execution:",
                "choices": [Choice(True, "Yes"), Choice(False, "No", enabled=True)],
                "default": data.get_allow_code_execution(),
                "long_instruction": "Be careful if turning this on this only effects file_format,metadata, and dir_format",
            },
            {
                "type": "filepath",
                "name": "temp_dir",
                "message": "Location to store temp file",
                "default": data.get_TempDir() or "",
                "long_instruction": "Leave empty to use default location",
            },
            {
                "type": "list",
                "name": "",
                "message": "append logs into daily log files",
                "default": data.get_appendlog(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
            {
                "type": "list",
                "name": "sanitize_text",
                "message": "Remove special characters when inserting text in db",
                "default": data.get_sanitizeDB(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
            {
                "type": "list",
                "name": "text_type",
                "message": "How the textlimit should be interpreted as",
                "default": data.get_textType(),
                "choices": [
                    Choice("word", "Word Count"),
                    Choice("letter", "Letter Count"),
                ],
            },
            {
                "type": "list",
                "name": "truncation_default",
                "message": "Should the script truncate long",
                "default": data.get_truncation(),
                "choices": [
                    Choice(True, "Yes"),
                    Choice(False, "No"),
                ],
                "long_instruction": "Truncation is based on operating system",
            },
        ]
    )
    custom.update(new_settings)
    schema.get_current_config_schema({"config": custom})
    return custom


def config_prompt() -> dict:
    custom = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "main_profile",
                "message": "What would you like your main profile to be?",
                "default": data.get_main_profile(),
                "validate": EmptyInputValidator(),
            },
            {
                "type": "filepath",
                "name": "save_location",
                "message": "save_location: ",
                "long_instruction": "Where would you like to set as the root save downloaded directory?",
                "default": common_paths.get_save_location(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
                "validate": PathValidator(is_dir=True),
            },
            {
                "type": "input",
                "name": "file_size_limit",
                "message": "file_size_limit: ",
                "long_instruction": """
File size limit
Input can be int representing bytes
or human readable such as 10mb

Enter 0 for no limit
""",
                "default": str(data.get_filesize_limit()),
                "filter": int,
            },
            {
                "type": "input",
                "name": "file_size_min",
                "message": "file_size_min: ",
                "long_instruction": """
File size min
Input can be int representing bytes
or human readable such as 10mb

Enter 0 for no minimum
""",
                "default": str(data.get_filesize_min()),
                "filter": int,
            },
            {
                "type": "input",
                "name": "system_free_min",
                "message": "minimum free space: ",
                "long_instruction": """
Minimum freespace for download
Input can be int representing bytes
or human readable such as 10mb

Enter 0 for no limit
""",
                "default": str(data.get_system_freesize()),
                "filter": int,
            },
            {
                "type": "input",
                "name": "dir_format",
                "message": "dir_format: ",
                "long_instruction": "What format do you want for download directories",
                "default": data.get_dirformat(),
            },
            {
                "type": "input",
                "name": "file_format",
                "message": "What format do you want for downloaded files",
                "default": data.get_fileformat(),
            },
            {
                "type": "number",
                "name": "textlength",
                "message": "textlength: ",
                "long_instruction": "Enter the max length to extract for post text, 0 means unlimited\n",
                "default": data.get_textlength(),
                "min_allowed": 0,
                "validate": EmptyInputValidator(),
            },
            {
                "type": "input",
                "name": "space-replacer",
                "message": "space-replacer: ",
                "long_instruction": "Replace any spaces in text with this character\n",
                "default": data.get_spacereplacer(),
            },
            {
                "type": "input",
                "name": "date",
                "message": "date: ",
                "long_instruction": "Enter Date format",
                "default": data.get_date(),
                "validate": prompt_validators.dateplaceholdervalidator(),
            },
            {
                "type": "input",
                "name": "metadata",
                "message": "metadata: ",
                "long_instruction": "Where should metadata files be saved",
                "default": data.get_metadata(),
            },
            {
                "type": "checkbox",
                "name": "filter",
                "message": "filter: ",
                "choices": list(
                    map(
                        lambda x: Choice(
                            name=x,
                            value=x,
                            enabled=x.capitalize() in set(data.get_filter()),
                        ),
                        constants.getattr("FILTER_DEFAULT"),
                    )
                ),
                "validate": prompt_validators.emptyListValidator(),
            },
            {
                "type": "filepath",
                "name": "mp4decrypt",
                "message": "mp4decrypt path: ",
                "validate": prompt_validators.MultiValidator(
                    EmptyInputValidator(),
                    prompt_validators.mp4decryptpathvalidator(),
                    prompt_validators.mp4decryptexecutevalidator(),
                ),
                "default": data.get_mp4decrypt(),
                "long_instruction": """
Certain content requires decryption to process please provide the full path to mp4decrypt
""",
            },
            {
                "type": "filepath",
                "name": "ffmpeg",
                "message": "ffmpeg path: ",
                "validate": prompt_validators.MultiValidator(
                    EmptyInputValidator(),
                    prompt_validators.ffmpegpathvalidator(),
                    prompt_validators.ffmpegexecutevalidator(),
                ),
                "long_instruction": """
Certain content requires decryption to process please provide the full path to ffmpeg
""",
                "default": data.get_ffmpeg(),
            },
            {
                "type": "input",
                "name": "discord",
                "message": "discord webhook: ",
                "validate": prompt_validators.DiscordValidator(),
                "default": data.get_discord(),
            },
        ]
    )
    console.print("Set mapping for {responsetype} placeholder\n\n")

    answer2 = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "timeline",
                "long_instruction": """
set responsetype for timeline posts
Empty string is consider to be 'posts'
            """,
                "default": data.get_timeline_responsetype(),
                "message": "timeline responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "archived",
                "long_instruction": """
set responsetype for archived posts
Empty string is consider to be 'archived'
            """,
                "default": data.get_archived_responsetype(),
                "message": "archived responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "pinned",
                "long_instruction": """
set responsetype for pinned posts
Empty string is consider to be 'pinned'
            """,
                "default": data.get_pinned_responsetype(),
                "message": "pinned responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "message",
                "long_instruction": """
set responsetype for message posts
Empty string is consider to be 'message'
            """,
                "default": data.get_messages_responsetype(),
                "message": "message responstype mapping: ",
            },
            {
                "type": "input",
                "name": "paid",
                "long_instruction": """
set responsetype for paid posts
Empty string is consider to be 'paid'
            """,
                "default": data.get_paid_responsetype(),
                "message": "paid responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "stories",
                "long_instruction": """
set responsetype for stories
Empty string is consider to be 'stories'
            """,
                "default": data.get_stories_responsetype(),
                "message": "stories responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "highlights",
                "long_instruction": """
set responsetype for highlights
Empty string is consider to be 'highlights'
            """,
                "default": data.get_highlights_responsetype(),
                "message": "highlight responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "profile",
                "long_instruction": """
set responsetype for profile
Empty string is consider to be 'profile'
            """,
                "default": data.get_profile_responsetype(),
                "message": "profile responsetype mapping: ",
            },
        ]
    )
    answer["responsetype"] = answer2
    custom.update(answer)
    schema.get_current_config_schema({"config": custom})
    return custom


def reset_username_prompt() -> bool:
    name = "reset username"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to reset username info",
                "choices": [
                    Choice("Selection", "Yes Update Selection"),
                    Choice("Data", "Yes Refetch Data"),
                    "No",
                ],
                "default": "No",
            }
        ]
    )

    return answer[name]


def reset_areas_prompt() -> bool:
    name = "reset areas"
    print(f"Download Area: {areas.get_download_area()}")
    print(f"Like Area: {areas.get_like_area()}")
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to reset selected area(s)",
                "choices": [
                    Choice("Download", "Download area only"),
                    Choice("Like", "Like area only"),
                    "Both",
                    "No",
                ],
                "default": "No",
            }
        ]
    )
    return answer[name]


def reset_like_areas_prompt() -> bool:
    name = "reset areas"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to reset the selected like area",
                "choices": ["Yes", "No"],
                "default": "No",
            }
        ]
    )

    return answer[name]


def reset_download_areas_prompt() -> bool:
    name = "reset areas"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to reset the selected download area(s)",
                "choices": ["Yes", "No"],
                "default": "No",
            }
        ]
    )

    return answer[name]


def mp4_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "filepath",
                "name": "mp4decrypt",
                "message": "mp4decrypt path: ",
                "validate": prompt_validators.MultiValidator(
                    EmptyInputValidator(),
                    prompt_validators.mp4decryptpathvalidator(),
                    prompt_validators.mp4decryptexecutevalidator(),
                ),
                "long_instruction": """
Certain content requires decryption to process please provide the full path to mp4decrypt
Linux version [mp4decrypt] and windows version [mp4decrypt.exe] are provided in the repo

https://www.bento4.com/documentation/mp4decrypt/
""",
                "default": data.get_mp4decrypt(),
            },
        ]
    )

    return answer["mp4decrypt"]


def ffmpeg_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "filepath",
                "name": "ffmpeg",
                "message": "ffmpeg path: ",
                "validate": prompt_validators.MultiValidator(
                    EmptyInputValidator(),
                    prompt_validators.ffmpegpathvalidator(),
                    prompt_validators.ffmpegexecutevalidator(),
                ),
                "long_instruction": """
Certain content requires decryption to process please provide the full path to ffmpeg
Linux version [ffmpeg] and windows version [ffmpeg.exe] are provided in the repo 

https://ffmpeg.org/download.html
""",
                "default": data.get_ffmpeg(),
            },
        ]
    )

    return answer["ffmpeg"]


def auto_download_mp4_decrypt() -> bool:
    name = "manual download"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "mp4decrypt not found would you like to auto install?",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer[name]


def auto_download_ffmpeg() -> bool:
    name = "manual download"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "ffmpeg not found would you like to auto install?",
                "choices": ["Yes", "No"],
            }
        ]
    )
    return answer[name]


def continue_prompt() -> bool:
    name = "continue"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to continue with script",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer[name]


def model_selector(models) -> bool:
    choices = list(
        map(lambda x: modelHelpers.model_selectorHelper(x[0], x[1]), enumerate(models))
    )

    def funct(prompt):
        oldargs = copy.deepcopy(vars(read_args.retriveArgs()))
        userselector.setfilter()
        userselector.setsort()
        if oldargs != vars(read_args.retriveArgs()):
            nonlocal models
            models = userselector.filterNSort(userselector.ALL_SUBS)
        choices = list(
            map(
                lambda x: modelHelpers.model_selectorHelper(x[0], x[1]),
                enumerate(models),
            )
        )
        selectedSet = set(
            map(
                lambda x: re.search("^[0-9]+: ([^ ]+)", x["name"]).group(1),
                prompt.selected_choices or [],
            )
        )
        for model in choices:
            name = re.search("^[0-9]+: ([^ ]+)", model.name).group(1)
            if name in selectedSet:
                model.enabled = True
        prompt.content_control._raw_choices = choices
        prompt.content_control.choices = prompt.content_control._get_choices(
            prompt.content_control._raw_choices, prompt.content_control._default
        )
        prompt.content_control._format_choices()
        return prompt

    def funct2(prompt_):
        selected = prompt_.content_control.selection["value"]
        console.print(
            f"""
        Name: [bold blue]{selected.name}[/bold blue]
        ID: [bold blue]{selected.id}[/bold blue]
        Renewed Date: [bold blue]{selected.renewed_string}[/bold blue]
        Subscribed Date: [bold blue]{selected.subscribed_string}[/bold blue]
        Expired Date: [bold blue]{selected.expired_string}[/bold blue]
        Last Seen: [bold blue] {selected.last_seen_formatted}[/bold blue]
        Original Sub Price: [bold blue]{selected.sub_price}[/bold blue]     [Current Subscription Price]
        Original Regular Price: [bold blue]{selected.regular_price}[/bold blue]     [Regular Subscription Price Set By Model]
        Original Claimable Promo Price: [bold blue]{selected.lowest_promo_claim}[/bold blue]   [Lowest Promotional Price Marked as Claimable]
        Original Any Promo Price: [bold blue]{selected.lowest_promo_all}[/bold blue]     [Lowest of Any Promotional Price]
        
        ------------------------------------------------------------------------------------------------------------------------------------
        Final Current Price: [bold blue]{selected.final_current_price}[/bold blue] [Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
        Final Promo Price: [bold blue]{selected.final_promo_price}[/bold blue] [Lowest Any Promo Price or Regular Price | See Final Price Details]
        Final Renewal Price: [bold blue]{selected.final_renewal_price}[/bold blue] [Lowest Claimable Promo or Regular Price | See Final Price Details]
        Final Regular Price: [bold blue]{selected.final_regular_price}[/bold blue] [Regular Price | See Final Price Details]
        
        [italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]

        ======================================================
        
        PRESS ENTER TO RETURN
        """
        )
        prompt("")

    p = promptClasses.getFuzzySelection(
        choices=choices,
        transformer=lambda result: ",".join(map(lambda x: x.split(" ")[1], result)),
        multiselect=True,
        long_instruction=prompt_strings.MODEL_SELECT,
        long_message=prompt_strings.MODEL_FUZZY,
        altx=funct,
        altd=funct2,
        validate=prompt_validators.emptyListValidator(),
        prompt="Filter: ",
        message="Which models do you want to scrape\n:",
        info=True,
    )

    return p


def decide_filters_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "input",
                "default": "No",
                "message": "Modify filters for your accounts list?\nSome usage examples are scraping free accounts only or paid accounts without renewal",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer["input"]


def modify_filters_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "renewal",
                "default": None,
                "message": "Filter account by whether it has a renewal date",
                "choices": [
                    Choice(True, "Active Only"),
                    Choice(False, "Disabled Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "expire",
                "default": None,
                "message": "Filter accounts based on access to content via a subscription",
                "choices": [
                    Choice(True, "Active Only"),
                    Choice(False, "Expired Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "last-seen",
                "default": None,
                "message": "Filter Accounts By whether the account by the visability of last seen",
                "choices": [
                    Choice(True, "Last seen is present"),
                    Choice(False, "Last seen is hidden"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "promo",
                "message": "Filter accounts presence of claimable promotions",
                "default": None,
                "choices": [
                    Choice(True, "Promotions Only"),
                    Choice(False, "No Promotions"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "all-promo",
                "message": "Filter accounts presence of any promotions",
                "default": None,
                "choices": [
                    Choice(True, "Promotions Only"),
                    Choice(False, "No Promotions"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "free-trial",
                "default": None,
                "message": "Filter Accounts By whether the account is a free trial",
                "choices": [
                    Choice(True, "Free Trial only"),
                    Choice(False, "Paid and always free accounts"),
                    Choice(None, "Any Account"),
                ],
            },
        ]
    )

    args.renewal = answer["renewal"]
    args.sub_status = answer["expire"]
    args.promo = answer["promo"]
    args.all_promo = answer["all-promo"]
    args.free_trial = answer["free-trial"]
    args.last_seen = answer["last-seen"]
    if args.free_trial != "yes":
        args = modify_current_price(args)
    if args.free_trial != "yes" and decide_price_prompt() == "Yes":
        args = modify_other_prices(args)
    return args


def modify_current_price(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "subscription",
                "message": "Filter accounts by the type of a current subscription price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Subscriptions Only"),
                    Choice("free", "Free Subscriptions Only"),
                    Choice(None, "Both"),
                ],
            },
        ]
    )

    args.current_price = answer["subscription"]
    return args


def decide_price_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "input",
                "default": "No",
                "message": "Would you like to modify other price types",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer["input"]


def modify_other_prices(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "regular",
                "message": "Filter accounts by the regular subscription price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Subscriptions Only"),
                    Choice("free", "Free Subscriptions Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "future",
                "message": "Filter accounts by renewal price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Renewals Only"),
                    Choice("free", "Free Renewals Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "promo-price",
                "message": "Filter accounts by any promotional price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Promotions"),
                    Choice("free", "Free Promotions"),
                    Choice(None, "Both"),
                ],
            },
        ]
    )

    args.regular_price = answer["regular"]
    args.renewal_price = answer["future"]
    args.promo_price = answer["promo-price"]
    return args


def decide_sort_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "input",
                "message": f"Change the Order or the Criteria for how the model list is sorted\nCurrent setting are {read_args.retriveArgs().sort.capitalize()} in {'Ascending' if not read_args.retriveArgs().desc else 'Descending'} order",
                "default": "No",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer["input"]


def modify_sort_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "type",
                "message": "Sort Accounts by..",
                "default": args.desc == False,
                "choices": [
                    Choice("name", "By Name"),
                    Choice("subscribed", "Subscribed Date"),
                    Choice("expired", "Expiring Date"),
                    Choice("last-seen", "Last Seen"),
                    Choice("current-price", "Current Price"),
                    Choice("promo-price", "Promotional Price"),
                    Choice("regular-price", "Regular Price"),
                    Choice("renewal-price", "Renewal Price"),
                ],
            },
            {
                "type": "list",
                "name": "order",
                "message": "Sort Direction",
                "choices": [
                    Choice(True, "Ascending"),
                    Choice(False, "Descending", enabled=True),
                ],
                "default": True,
            },
        ]
    )

    args.sort = answer["type"]
    args.desc = answer["order"] == False
    return args


def change_default_profile() -> bool:
    name = "reset username"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Set this as the new default profile",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer[name]


def reset_config_prompt() -> bool:
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "How do you want to fix this issue",
                "choices": ["Reset Default", "Manually Edit Config"],
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


def manual_config_prompt(configText) -> str:
    name = "input"

    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "multiline": True,
                "name": name,
                "default": configText,
                "long_message": prompt_strings.MULTI,
                "message": "Edit config text\n===========\n",
            }
        ]
    )

    return questions[name]


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


def get_speed(threads):
    logging.getLogger("shared").info("running speed test")
    speed = system.speed_test()
    thread_count = int(threads["threads"])
    if int(thread_count) == 0:
        max_allowed = min(
            max((speed * 0.6) // constants.getattr("maxChunkSize"), 3) * 2, 100
        )
    else:
        max_allowed = min(
            int(
                max(
                    ((speed * 0.6) / thread_count)
                    // constants.getattr("maxChunkSizeB"),
                    3,
                )
                * 2
            ),
            100 // thread_count,
        )
    return max_allowed


def retry_user_scan():
    answer = promptClasses.getChecklistSelection(
        message="Rescan account for users",
        choices=[Choice(True, "Yes"), Choice(False, "No")],
    )

    return answer
