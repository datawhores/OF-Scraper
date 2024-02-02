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
import os

from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from InquirerPy.validator import EmptyInputValidator, PathValidator
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.cache as cache
import ofscraper.utils.config.custom as custom
import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.constants as constants
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.system as system

console = Console()


def funct(prompt_):
    console.print(
        f"""
    For more Details => https://of-scraper.gitbook.io/of-scraper/config-options
    
    [General Options]
    main_profile: default profile attached to config
    metadata: path to save db files
    discord: discord hook for logging
    -----------------------------------
    [File Options]
    save_location: root directory for files
    dir_format: format of directories
    file_format: format of filenames
    textlength: max length of text placeholder
    space-replacer: space replacement for filenames
    date: date format for placeholders
    text_type_default: toggle for word count type
    trunication_default: toggle for trunicating filenames
    -----------------------------------
    [Download Options]
    file_size_limit: max size allowed for download
    file_size_min: min size required for download
    filter: which media to download
    auto_resume: toggle for resuming downloads
    system_free_min: stops downloads when bypass
    -----------------------------------
    [Binary Options]
    mp4decrypt: path to mp4decrypt binary
    ffmeg: path to ffmpeg binary
    -----------------------------------
    [CDM Options]
    private-key: for manual cdm
    client-id: for manual cdm
    key-mode-default: which cdm
    keydb_api: for keydb cdm
    -----------------------------------
    [Performance Options]
    download-sems: number of downloads per processor/worker
    threads: number of processors/workers
    -----------------------------------
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
    disable_after_check: toggle for safe --after usage
    default_user_list: default user list for --action
    default_black_list: default black list for --action
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
    config_prompt_choices.insert(6, Separator())
    config_prompt_choices.insert(9, Separator())

    answer = promptClasses.getChecklistSelection(
        message="Config Menu: Which area would you like to change?",
        choices=[*config_prompt_choices],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
    )
    return constants.getattr("configPromptChoices")[answer]


def download_config():
    out = {}
    answer = promptClasses.batchConverter(
        *[
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
                "type": "list",
                "name": "auto_resume",
                "message": "Enable auto file resume",
                "long_instruction": "Enable this if you don't want to auto resume files, and want .part files auto cleaned",
                "default": data.get_part_file_clean(),
                "choices": [Choice(True, "Yes"), Choice(False, "No")],
            },
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
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
                "long_instruction": "Where would you like to set as the root save downloaded directory?",
                "default": common_paths.get_save_location(),
                "filter": lambda x: prompt_validators.cleanTextInput(x),
                "validate": PathValidator(is_dir=True),
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
                "type": "list",
                "name": "text_type_default",
                "message": "date: ",
                "long_instruction": "How should textlength be interpreted",
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
                "long_instruction": "Truncation is based on operating system",
            },
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
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
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
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
                "long_instruction": "Required if your using keydb for key-mode",
                "default": data.get_keydb_api() or "",
            },
            {
                "type": "filepath",
                "name": "client-id",
                "message": "Enter path to client id file",
                "long_instruction": "Required if your using manual for key-mode",
                "default": data.get_client_id() or "",
            },
            {
                "type": "filepath",
                "name": "private-key",
                "message": "Enter path to private-key",
                "long_instruction": "Required if your using manual for key-mode",
                "default": data.get_private_key() or "",
            },
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
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
                "name": "threads",
                "message": "Number of Download processes/threads: ",
                "min_allowed": 0,
                "max_allowed": os.cpu_count() - 1,
                "validate": EmptyInputValidator(),
                "long_instruction": f"Value can be 1-{os.cpu_count()-1}",
                "default": data.get_threads(),
            },
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
    )

    out.update(threads)
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
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "number",
                "name": "download-sems",
                "message": "Number of semaphores per thread: ",
                "min_allowed": 1,
                "max_allowed": max_allowed,
                "validate": EmptyInputValidator(),
                "long_instruction": f"Value can be 1-{max_allowed}",
                "default": data.get_download_semaphores(),
            }
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
    )
    out.update(answer)
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
                "long_instruction": "Where should metadata files be saved",
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
        long_instruction=prompt_strings.CONFIG_MENU,
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
                "name": "backend",
                "choices": [Choice("aio", "aiohttp"), Choice("httpx", "httpx")],
                "message": "Select Which Backend you want:\n",
                "default": data.get_backend() or "",
            },
            # value because of legacy config values
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
                "long_instruction": "Allows for use of eval to evaluate custom values in placeholders",
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
                "long_instruction": "Action Mode is when at least one --action is based as an arg or --scrape-paid",
            },
            {
                "type": "list",
                "name": "disable_after_check",
                "message": "Disable After Check",
                "default": data.get_disable_after(),
                "choices": [
                    Choice(True, "Yes"),
                    Choice(False, "No"),
                ],
                "long_instruction": "This will disable full scan on when previous scan used --after",
            },
            {
                "type": "input",
                "name": "default_user_list",
                "message": "Default User Lists",
                "default": data.get_default_userlist(),
                "long_instruction": """
A comma seperated list of userlists to set as default when retriving users
Main user list with all active+expired users can be called main or ofscraper.main
Active user list can be called active or ofscraper.active
Expired user list can be called expired or ofscraper.expired
List are case insensitive",
""",
            },
            {
                "type": "input",
                "name": "default_black_list",
                "message": "Default User Black Lists",
                "default": data.get_default_blacklist(),
                "long_instruction": """
A comma seperated list of userlists to set as black listed
Main user list with all active+expired users can be called main or ofscraper.main
Active user list can be called active or ofscraper.active
Expired user list can be called expired or ofscraper.expired
List are case insensitive",
""",
            },
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
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
        ],
        altx=funct,
        long_instruction=prompt_strings.CONFIG_MENU,
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
                    Choice("manual", "Through script Edit Config"),
                    Choice("again", "File was fixed manually"),
                ],
            }
        ]
    )
    return questions[name]
