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
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.constants as constants


def main_prompt() -> int:
    main_prompt_choices = [*constants.getattr("mainPromptChoices")]
    main_prompt_choices.insert(1, Separator())
    main_prompt_choices.insert(6, Separator())
    answer = promptClasses.getChecklistSelection(
        message="Main Menu: What would you like to do?", choices=[*main_prompt_choices]
    )
    return constants.getattr("mainPromptChoices")[answer]


def action_prompt() -> int:
    action_prompt_choices = [*constants.getattr("ActionPromptChoices")]
    action_prompt_choices.insert(3, Separator())
    action_prompt_choices.insert(6, Separator())
    action_prompt_choices.insert(9, Separator())
    answer = promptClasses.getChecklistSelection(
        message="Action Menu: What action(s) would you like to take?",
        choices=[*action_prompt_choices],
    )
    args = read_args.retriveArgs()
    action = constants.getattr("ActionPromptChoices")[answer]
    if isinstance(action, str):
        return action
    args.action = action
    write_args.setArgs(args)


def continue_prompt() -> bool:
    if not constants.getattr("CONTINUE_BOOL"):
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
