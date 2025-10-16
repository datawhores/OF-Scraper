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

from InquirerPy.separator import Separator
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.of_env.of_env as of_env


def main_prompt() -> int:
    main_prompt_choices = [*of_env.getattr("mainPromptChoices")]
    main_prompt_choices.insert(1, Separator())
    main_prompt_choices.insert(6, Separator())
    answer = promptClasses.getChecklistSelection(
        message="Main Menu: What would you like to do?", choices=[*main_prompt_choices]
    )
    return of_env.getattr("mainPromptChoices")[answer]


def continue_prompt() -> bool:
    if not of_env.getattr("CONTINUE_BOOL"):
        return False
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
