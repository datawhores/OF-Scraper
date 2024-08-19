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
import math

from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from InquirerPy.validator import EmptyInputValidator, PathValidator
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.config.custom as custom
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.config.data as data

console = Console()


def funct(prompt_):
    console.print(
        """
    For more Details => https://of-scraper.gitbook.io/of-scraper/config-options
    
    [General Options]
    main_profile: default profile attached to config
    metadata: path to save db files
    discord: discord hook for logging
    -----------------------------------
    [File Options]:
    save_location: root directory for files
    dir_format: format of directories
    textlength: max length of text placeholder
    space_replacer: space replacement for filenames
    date: date format for placeholders
    text_type_default: toggle for word count type
    trunication_default: toggle for trunicating filenames
    audio: optional overwrites for audio
    videos: optional overwrites for video
    images: optional overwrties from images
    -----------------------------------
    [Download Options]
    file_size_max: max size allowed for download
    file_size_min: min size required for download
    length_min: min length of media, only applies to videos
    length_max: max length of media, only applies to videos
    filter: which media types to download
    auto_resume: toggle for resuming downloads
    system_free_min: stops downloads when bypass
    -----------------------------------
    [Binary Options]
    ffmeg: path to ffmpeg binary
    -----------------------------------
    [Script Options]
    post_download_script: script to run after each model
    post_script: script to run after all models are processed
    -----------------------------------
    [CDM Options]
    private-key: for manual cdm
    client-id: for manual cdm
    key-mode-default: which cdm
    keydb_api: for keydb cdm
    -----------------------------------
    [Performance Options]
    download_sems: number of downloads per processor/worker
    thread_count: number of processors/workers
    download_limit: max download speed per second for each thread
    -----------------------------------
    [Content Filter Options]
    block_ads: use common key words to block ads
    --------------------------------------------------
    [Scripts Options]
    post_download_script: script to run after actions on each model
    post_script: script to run after all models are processed
    --------------------------------------------------
    [Advanced Options]
    code-execution: allow eval on custom_val
    dynamic-mode-default: source of signed header values
    backend: which downloader to utilize
    downloadbars: toggle for download-bars
    cache-mode: cache type for Disk Cache
    appendlog: toggle for appending log values
    custom_values: custom values/functions for placeholders
    sanitize_text: toggle for cleaning text for db
    temp_dir: directory for storing temp files
    infinite_loop_action_mode: toggle for infinite loop via action mode
    enable_auto_after: whether to dynamically set --after: default True
    default_user_list: default user list for --action
    default_black_list: default black list for --action
    remove_hash_match: remove files if hash matches
    ----------------------------------------------------------
    [Response Type]
    values that remap responsetypes for downloads
    ======================================================
    
    PRESS ENTER TO RETURN
    """
    )
    prompt("")
    return prompt_


def config_prompt() -> int:
    config_prompt_choices = [*constants.getattr("configPromptChoices")]
    config_prompt_choices.insert(8, Separator())
    config_prompt_choices.insert(11, Separator())

    answer = promptClasses.getChecklistSelection(
        message="Config Menu: Which area would you like to change?",
        choices=[*config_prompt_choices],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    return constants.getattr("configPromptChoices")[answer]


def download_config():
    out = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "system_free_min",
                "message": "minimum free space: ",
                "option_instruction": """
Minimum freespace for download
Input can be int representing bytes
or human readable such as 10mb

Enter 0 for no limit
""",
                "default": str(data.get_system_freesize()),
                "filter": lambda x: int(x) if x != "None" else 0,
            },
            {
                "type": "input",
                "name": "length_min",
                "message": "min length: ",
                "option_instruction": """
Min length of media to download in seconds
This only applies to videos
Enter 0 to disable
""",
                "default": str(data.get_min_length()),
                "filter": lambda x: int(x) if x != "None" else 0,
            },
            {
                "type": "input",
                "name": "length_max",
                "message": "max length: ",
                "option_instruction": """
Max length of media to download in seconds
This only applies to videos
Enter 0 to disable
""",
                "default": str(data.get_max_length()),
                "filter": lambda x: int(x) if x != "None" else 0,
            },
            {
                "type": "list",
                "name": "auto_resume",
                "message": "Enable auto file resume",
                "option_instruction": "Enable this if you don't want to auto resume files, and want .part files auto cleaned",
                "default": data.get_part_file_clean(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def file_config():
    out = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "filepath",
                "name": "save_location",
                "message": "save_location: ",
                "option_instruction": "Where would you like to set as the root save downloaded directory?",
                "default": common_paths.get_save_location(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
                "validate": PathValidator(is_dir=True),
            },
            {
                "type": "input",
                "name": "dir_format",
                "message": "dir_format: ",
                "option_instruction": "What format do you want for download directories",
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
                "option_instruction": "Enter the max length to extract for post text, 0 means unlimited\n",
                "default": data.get_textlength(),
                "min_allowed": 0,
                "validate": EmptyInputValidator(),
            },
            {
                "type": "input",
                "name": "space-replacer",
                "message": "space_replacer: ",
                "option_instruction": "Replace any spaces in text with this character\n",
                "default": data.get_spacereplacer(),
            },
            {
                "type": "input",
                "name": "date",
                "message": "date: ",
                "option_instruction": "Enter Date format",
                "default": data.get_date(),
                "validate": prompt_validators.dateplaceholdervalidator(),
            },
            {
                "type": "list",
                "name": "text_type_default",
                "message": "text type: ",
                "option_instruction": "How should textlength be interpreted",
                "default": data.get_textType(),
                "choices": [Choice("letter", "Letter"), Choice("word", "Word")],
                "validate": prompt_validators.emptyListValidator(),
            },
            {
                "type": "list",
                "name": "truncation_default",
                "message": "Should the script truncate long filenames",
                "default": data.get_truncation(),
                "choices": [
                    Choice(True, "Yes"),
                    Choice(False, "No"),
                ],
                "option_instruction": "Truncation is based on operating system",
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def binary_config():
    out = {}
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
                "option_instruction": """
Certain content requires decryption to process please provide the full path to ffmpeg
""",
                "default": settings.get_ffmpeg(),
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def script_config():
    out = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "post_download_script",
                "message": "Script to run after each model is processed",
                "default": data.get_post_download_script() or "",
                "option_instruction": "Leave empty to skip post download script",
            },
            {
                "type": "input",
                "name": "post_script",
                "message": "Script to run after all models have processed",
                "default": data.get_post_script() or "",
                "option_instruction": "Leave empty to skip post download script",
            },
        ],
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def cdm_config():
    out = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "key-mode-default",
                "message": "Select default key mode for decryption",
                "default": data.get_key_mode(),
                "choices": constants.getattr("KEY_OPTIONS"),
            },
            {
                "type": "input",
                "name": "keydb_api",
                "message": "keydb api key:\n",
                "option_instruction": "Required if your using keydb for key-mode",
                "default": data.get_keydb_api() or "",
            },
            {
                "type": "filepath",
                "name": "client-id",
                "message": "Enter path to client id file",
                "option_instruction": "Required if your using manual for key-mode",
                "default": data.get_client_id() or "",
            },
            {
                "type": "filepath",
                "name": "private-key",
                "message": "Enter path to private-key",
                "option_instruction": "Required if your using manual for key-mode",
                "default": data.get_private_key() or "",
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def performance_config():
    out = {}
    threads = promptClasses.batchConverter(
        *[
            {
                "type": "number",
                "name": "thread_count",
                "message": "Number of Download processes/threads: ",
                "min_allowed": 0,
                "max_allowed": 3,
                "validate": EmptyInputValidator(),
                "option_instruction": f"Value can be 1-3",
                "default": data.get_threads(),
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )

    out.update(threads)
    max_allowed = get_max_sems(threads)

    sems = promptClasses.batchConverter(
        *[
            {
                "type": "number",
                "name": "download_sems",
                "message": "Number of semaphores per thread: ",
                "min_allowed": 1,
                "max_allowed": max_allowed,
                "validate": EmptyInputValidator(),
                "option_instruction": f"Value can be 1-{max_allowed}",
                "default": data.get_download_semaphores(),
            }
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(sems)

    speed = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "download_limit",
                "message": "Maximum download speed per second for  each thread: ",
                "validate": EmptyInputValidator(),
                "option_instruction": """
                Input can be int representing bytes
                or human readable such as 10mb
                """,
                "default": str(data.get_download_limit()),
                "filter": lambda x: int(x) if x != "None" else 0,
            }
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(speed)

    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def general_config():
    out = {}
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
                "type": "input",
                "name": "metadata",
                "message": "metadata: ",
                "option_instruction": "Where should metadata files be saved",
                "default": data.get_metadata(),
            },
            {
                "type": "input",
                "name": "discord",
                "message": "discord webhook: ",
                "validate": prompt_validators.DiscordValidator(),
                "default": data.get_discord(),
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def content_config():
    out = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "block_ads",
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
                "message": "Do you want to auto block post with advertisment words:\n",
                "default": data.get_block_ads(),
            },
            {
                "type": "input",
                "name": "file_size_max",
                "message": "file_size_max: ",
                "option_instruction": """
File size limit
Input can be int representing bytes
or human readable such as 10mb

Enter 0 for no limit
""",
                "default": str(data.get_filesize_max()),
            },
            {
                "type": "input",
                "name": "file_size_min",
                "message": "file_size_min: ",
                "option_instruction": """
File size min
Input can be int representing bytes
or human readable such as 10mb

Enter 0 for no minimum
""",
                "default": str(data.get_filesize_min()),
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
        ],
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def advanced_config() -> dict:
    out = {}
    new_settings = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "dynamic-mode-default",
                "message": "What would you like to use for dynamic rules",
                "default": data.get_dynamic(),
                "choices": constants.DYNAMIC_OPTIONS,
            },
            {
                "type": "list",
                "name": "cache-mode",
                "message": "sqlite should be fine unless your using a network drive\nSee https://grantjenks.com/docs/diskcache/tutorial.html#caveats ",
                "default": data.cache_mode_helper(),
                "choices": ["sqlite", "json", "disabled", "api_disabled"],
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
                "type": "input",
                "name": "custom",
                "multiline": True,
                "message": "edit custom value:\n",
                "option_instruction": "This is a helper value for remapping placeholder values",
                "default": (
                    json.dumps(custom.get_custom())
                    if not isinstance(custom.get_custom(), str)
                    else custom.get_custom() or ""
                ),
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
                "option_instruction": "Allows for use of eval to evaluate custom values in placeholders",
            },
            {
                "type": "filepath",
                "name": "temp_dir",
                "message": "Location to store temp files",
                "default": data.get_TempDir() or "",
                "option_instruction": "Leave empty to use default location",
            },
            {
                "type": "list",
                "name": "appendlog",
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
                "name": "infinite_loop_action_mode",
                "message": "Run Program in infinite loop when in action mode",
                "default": data.get_InfiniteLoop(),
                "choices": [
                    Choice(True, "Yes"),
                    Choice(False, "No"),
                ],
                "option_instruction": "Action Mode is when at least one --action is based as an arg or --scrape-paid",
            },
            {
                "type": "list",
                "name": "enable_auto_after",
                "message": "Dynamically sets --after based on db and cache",
                "default": data.get_enable_after(),
                "choices": [
                    Choice(True, "Yes"),
                    Choice(False, "No"),
                ],
                "option_instruction": "This will disable full scan on when previous scan used --after",
            },
            {
                "type": "input",
                "name": "default_user_list",
                "message": "Default User Lists",
                "default": data.get_default_userlist(),
                "option_instruction": """
A comma seperated list of userlists to set as default when retriving users
Main user list with all active+expired users can be called main or ofscraper.main
Active user list can be called active or ofscraper.active
Expired user list can be called expired or ofscraper.expired
List are case insensitive\n
""",
            },
            {
                "type": "input",
                "name": "default_black_list",
                "message": "Default User Black Lists",
                "default": data.get_default_blacklist(),
                "option_instruction": """
A comma seperated list of userlists to set as black listed
Main user list with all active+expired users can be called main or ofscraper.main
Active user list can be called active or ofscraper.active
Expired user list can be called expired or ofscraper.expired
List are case insensitive\n
""",
            },
            {
                "type": "list",
                "name": "remove_hash_match",
                "message": "Remove Files by matching hashes",
                "default": data.get_hash(),
                "choices": [
                    Choice(True, "Hash Files and Remove Files"),
                    Choice(False, "Hash Files, but do not remove"),
                    Choice(None, "Don't Hash Files"),
                ],
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(new_settings)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema(config)
    return final


def response_type() -> dict:
    out = {}
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "timeline",
                "option_instruction": """
set responsetype for timeline posts
Empty string is consider to be 'posts'
            """,
                "default": data.get_timeline_responsetype(),
                "message": "timeline responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "archived",
                "option_instruction": """
set responsetype for archived posts
Empty string is consider to be 'archived'
            """,
                "default": data.get_archived_responsetype(),
                "message": "archived responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "pinned",
                "option_instruction": """
set responsetype for pinned posts
Empty string is consider to be 'pinned'
            """,
                "default": data.get_pinned_responsetype(),
                "message": "pinned responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "message",
                "option_instruction": """
set responsetype for message posts
Empty string is consider to be 'message'
            """,
                "default": data.get_messages_progress_responsetype(),
                "message": "message responstype mapping: ",
            },
            {
                "type": "input",
                "name": "paid",
                "option_instruction": """
set responsetype for paid posts
Empty string is consider to be 'paid'
            """,
                "default": data.get_paid_responsetype(),
                "message": "paid responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "stories",
                "option_instruction": """
set responsetype for stories
Empty string is consider to be 'stories'
            """,
                "default": data.get_stories_responsetype(),
                "message": "stories responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "highlights",
                "option_instruction": """
set responsetype for highlights
Empty string is consider to be 'highlights'
            """,
                "default": data.get_highlights_responsetype(),
                "message": "highlight responsetype mapping: ",
            },
            {
                "type": "input",
                "name": "profile",
                "option_instruction": """
set responsetype for profile
Empty string is consider to be 'profile'
            """,
                "default": data.get_profile_responsetype(),
                "message": "profile responsetype mapping: ",
            },
        ],
        altx=funct,
        more_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
    config = config_file.open_config()
    config.update(out)
    final = schema.get_current_config_schema({"config": config})
    return final


def manual_config_prompt(configText) -> str:
    name = "input"

    questions = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "multiline": True,
                "name": name,
                "default": configText,
                "long_message": prompt_strings.MULTI_LINE,
                "message": "Edit config text\n===========\n",
            }
        ]
    )

    return questions[name]


def get_max_sems(threads):
    thread_count = int(threads["thread_count"])
    max_allowed = math.ceil(15 / thread_count)
    return max_allowed


def retry_user_scan():
    answer = promptClasses.getChecklistSelection(
        message="Rescan account for users",
        choices=[Choice(True, "Yes"), Choice(False, "No")],
    )

    return answer


def reset_config_prompt() -> bool:
    name = "input"
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "How do you want to fix this issue",
                "choices": [
                    Choice("reset", "Reset Default"),
                    Choice("manual", "Edit Config manually with script"),
                    Choice("again", "File was fixed manually via text editor"),
                ],
            }
        ]
    )
    return questions[name]
