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
import ofscraper.utils.args.accessors.areas as areas
import ofscraper.utils.args.accessors.read as read_args
from ofscraper.utils.args.accessors.command import get_command



def areas_prompt() -> list:
    args = read_args.retriveArgs()
    name = "value"
    message = None
    print(args.command)
    if "like" in args.action and len(args.like_area) == 0:
        message = "Which area(s) would you do you want to download and like"
    elif "unlike" in args.action and len(args.like_area) == 0:
        message = "Which area(s) would you do you want to download and unlike"
    elif "download" in args.action and get_command()== "OF-Scraper":
        message = "Which area(s) would you do you want to download"
    more_instruction = (
        """Hint: Since you have Like or Unlike set
    You must select one or more of Timeline,Pinned,Archived, or Label
"""
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
                "more_instruction": more_instruction,
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
                    Choice("Streams"),
                ],
            }
        ]
    )
    
    answers[name].append(scrape_labels_prompt())
    return answers[name] if answers[name][-1] is not None else answers[name][:-1]


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
                    Choice("Streams"),
                ],
            }
        ]
    )
    answers[name].append(scrape_labels_prompt())
    return answers[name] if answers[name][-1] is not None else answers[name][:-1]


def download_areas_prompt() -> list:
    name = "areas"
    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": "Which area(s) would you to perform download actions on",
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
                    Choice("Streams"),
                ],
            }
        ]
    )
    answers[name].append(scrape_labels_prompt())
    return answers[name] if answers[name][-1] is not None else answers[name][:-1]


def metadata_areas_prompt() -> list:
    name = "areas"

    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": "Which area(s) would you to perform metadata actions on",
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
                    Choice("Streams"),
                ],
            }
        ]
    )
    answers[name].append(scrape_labels_prompt())
    return answers[name] if answers[name][-1] is not None else answers[name][:-1]


def db_areas_prompt() -> list:
    name = "areas"

    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": "Which area(s) would you to database  information from",
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
                    Choice("Streams"),
                ],
            }
        ]
    )
    return answers[name]

def metadata_anon_areas_prompt() -> list:
    name = "areas"
    answers = promptClasses.batchConverter(
        *[
            {
                "type": "checkbox",
                "qmark": "[?]",
                "name": name,
                "message": "Which area(s) would you to perform metadata actions on anonymously",
                "validate": prompt_validators.emptyListValidator(),
                "choices": [
                    Choice("Profile"),
                    Choice("Timeline"),
                    Choice("Pinned"),
                    Choice("Archived"),
                    Choice("Streams"),
                ],
            }
        ]
    )
    answers[name].append(scrape_labels_prompt())
    return answers[name] if answers[name][-1] is not None else answers[name][:-1]


def scrape_labels_prompt():
    name = "value"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Scrape labels\n[This is mainly for data enhancement]",
                "choices": [Choice(True, "True"), Choice(False, "False", enabled=True)],
                "default": False,
            },
        ]
    )
    if answer[name]:
        return "Labels"
    return


def scrape_paid_prompt():
    name = "value"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Scrape entire paid page\n\n[Warning: initial Scan can be slow]\n[Caution: You should not need this unless you are looking to scrape paid content from a deleted/banned model]",
                "choices": [Choice(True, "True"), Choice(False, "False", enabled=True)],
                "long_instruction": prompt_strings.SCRAPE_PAID,
                "default": False,
            },
        ]
    )

    return answer[name]


def reset_areas_prompt() -> bool:
    name = "reset areas"
    print(
        f"\n\nDownload Area: {areas.get_download_area() if bool(areas.get_download_area()) else None}"
    )
    print(
        f"Like Area: {areas.get_like_area() if bool(areas.get_like_area()) else None}\n\n"
    )
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to reset selected area(s)",
                "choices": [
                    Choice("Download", "Download area only + Scrape Paid"),
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
