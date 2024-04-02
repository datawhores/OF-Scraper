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
from InquirerPy.validator import EmptyInputValidator
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.constants as constants


def profiles_prompt() -> int:
    name = "profile"
    profile_prompt_choices = [*constants.getattr("profilesPromptChoices")]
    profile_prompt_choices.insert(5, Separator())

    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Profile Menu: Select one of the following:",
                "choices": profile_prompt_choices,
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
