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
import ofscraper.utils.const as const
import ofscraper.utils.settings as settings


_ALL_AREAS = (
    "Profile",
    "Timeline",
    "Pinned",
    "Archived",
    "Highlights",
    "Stories",
    "Messages",
    "Purchased",
    "Streams",
)
_LIKE_AREAS = const.TIMELINE_POST_AREAS
_ANON_AREAS = ("Profile", *const.TIMELINE_POST_AREAS)


def _areas_prompt(
    message,
    choices,
    *,
    name="areas",
    validate=None,
    with_labels=True,
    more_instruction=None,
) -> list:
    prompt_cfg = {
        "type": "checkbox",
        "qmark": "[?]",
        "name": name,
        "message": message,
        "validate": validate or prompt_validators.emptyListValidator(),
        "choices": [Choice(c) for c in choices],
    }
    if more_instruction is not None:
        prompt_cfg["more_instruction"] = more_instruction
    answers = promptClasses.batchConverter(prompt_cfg)
    if with_labels:
        answers[name].append(scrape_labels_prompt())
        return answers[name] if answers[name][-1] is not None else answers[name][:-1]
    return answers[name]


def areas_prompt() -> list:
    args = settings.get_args()
    message = None
    if "like" in args.actions and len(args.like_area) == 0:
        message = "Which area(s) would you do you want to download and like"
    elif "unlike" in args.actions and len(args.like_area) == 0:
        message = "Which area(s) would you do you want to download and unlike"
    elif "download" in args.actions and settings.get_settings().command == "OF-Scraper":
        message = "Which area(s) would you do you want to download"
    more_instruction = (
        """Hint: Since you have Like or Unlike set
    You must select one or more of Timeline,Pinned,Archived, or Label
"""
        if ("like" in args.actions or "unlike" in args.actions)
        and len(args.like_area) == 0
        else ""
    )
    return _areas_prompt(
        message,
        _ALL_AREAS,
        name="value",
        validate=prompt_validators.MultiValidator(
            prompt_validators.emptyListValidator(),
            prompt_validators.like_area_validator_posts(),
        ),
        more_instruction=more_instruction,
    )


def like_areas_prompt(like=True) -> list:
    return _areas_prompt(
        f"Which area(s) would you to perform {'like' if like else 'unlike'} actions on",
        _LIKE_AREAS,
    )


def download_areas_prompt() -> list:
    return _areas_prompt(
        "Which area(s) would you to perform download actions on",
        _ALL_AREAS,
    )


def metadata_areas_prompt() -> list:
    return _areas_prompt(
        "Which area(s) would you to perform metadata actions on",
        _ALL_AREAS,
    )


def db_areas_prompt() -> list:
    return _areas_prompt(
        "Which area(s) would you to database  information from",
        _ALL_AREAS,
        with_labels=False,
    )


def metadata_anon_areas_prompt() -> list:
    return _areas_prompt(
        "Which area(s) would you to perform metadata actions on anonymously",
        _ANON_AREAS,
    )


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


def _yes_no_reset_prompt(message):
    name = "reset areas"
    answer = promptClasses.batchConverter(
        {
            "type": "list",
            "name": name,
            "message": message,
            "choices": ["Yes", "No"],
            "default": "No",
        }
    )
    return answer[name]


def reset_like_areas_prompt() -> bool:
    return _yes_no_reset_prompt("Do you want to reset the selected like area")


def reset_download_areas_prompt() -> bool:
    return _yes_no_reset_prompt("Do you want to reset the selected download area(s)")
