from InquirerPy.separator import Separator
import arrow
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.constants as constants
from InquirerPy.base import Choice



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
    if "download" in action and not args.redownload:
        args=redownload_prompt()
    if isinstance(action, str):
        return action
    args.action = action
    write_args.setArgs(args)


def redownload_prompt() -> int:
    args = read_args.retriveArgs()
    answer = promptClasses.getChecklistSelection(
        message="Would you like to redownload all files",
        choices=[Choice(True,"Yes"),Choice(False,"No")]
    )
    if answer:
        args.force_all=True
        args.no_api_cache=True
        args.after=arrow.get(2000)
    return args