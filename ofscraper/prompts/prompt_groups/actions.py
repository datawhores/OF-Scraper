from InquirerPy.separator import Separator
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.constants as constants


def action_prompt() -> int:
    action_prompt_choices = [*constants.getattr("actionPromptChoices")]
    action_prompt_choices.insert(3, Separator())
    action_prompt_choices.insert(6, Separator())
    action_prompt_choices.insert(9, Separator())
    answer = promptClasses.getChecklistSelection(
        message="Action Menu: What action(s) would you like to take?",
        choices=[*action_prompt_choices],
    )
    args = read_args.retriveArgs()
    action = constants.getattr("actionPromptChoices")[answer]
    if isinstance(action, str):
        return action
    args.action = action
    write_args.setArgs(args)
