from InquirerPy.separator import Separator
import arrow
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.of_env.of_env as of_env
from InquirerPy.base import Choice
import ofscraper.utils.settings as settings




def action_prompt() -> int:
    action_prompt_choices = [*of_env.getattr("actionPromptChoices")]
    action_prompt_choices.insert(3, Separator())
    action_prompt_choices.insert(6, Separator())
    action_prompt_choices.insert(9, Separator())
    answer = promptClasses.getChecklistSelection(
        message="Action Menu: What action(s) would you like to take?",
        choices=[*action_prompt_choices],
    )
    args = settings.get_args()
    action = of_env.getattr("actionPromptChoices")[answer]
    if "download" in action and not args.redownload:
        args = redownload_prompt()
    if isinstance(action, str):
        return action
    args.action = action
    settings.update_args(args)


def redownload_prompt() -> int:
    args = settings.get_args()
    answer = promptClasses.getChecklistSelection(
        message="Would you like to redownload all files",
        choices=[Choice(True, "Yes"), Choice(False, "No")],
        default=False
    )
    if answer:
        args.force_all = True
        args.no_api_cache = True
        args.after = arrow.get(2000)
    return args
