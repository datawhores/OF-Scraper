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
from InquirerPy.base import Choice
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args


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
        "Hint: Since you have Like or Unlike Set\nYou must select one or more of Timeline,Pinned,Archived, or Label "
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


def reset_areas_prompt() -> bool:
    name = "reset areas"
    print(f"\n\nDownload Area: {areas.get_download_area()}")
    print(f"Like Area: {areas.get_like_area()}\n\n")
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
                "long_instruction": "like area is used for like and unlike\ndownload area is used for download",
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
