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
import copy
import json
import logging
import os
import re
import sys

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
import copy
import json
import logging
import os
import re
import sys

from InquirerPy.validator import EmptyInputValidator
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.config.data as data


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
