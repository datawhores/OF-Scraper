from InquirerPy.separator import Separator
import arrow
from prompt_toolkit.shortcuts import prompt as prompt

import ofscraper.data.api.common.scan_range as scan_range
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.of_env.of_env as of_env
from InquirerPy.base import Choice
import ofscraper.utils.settings as settings

# what a Yes to the redownload question changes, for that run only
REDOWNLOAD_ARGS = ("after", "force_all", "no_api_cache")
# their values from the command line, before any answer changed them
_session_values = None


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
    if isinstance(action, str):
        return action
    # each run starts from the session's own settings: a Yes on an earlier
    # run doesn't carry over to this one (#433)
    restore_session_values(args)
    if "download" in action and not args.redownload:
        args = redownload_prompt(args)
    args.actions = action
    # from here on the actions come from this prompt, not a command line
    scan_range.mark_actions_prompted()
    settings.update_args(args)


def restore_session_values(args):
    global _session_values
    if _session_values is None:
        _session_values = {key: getattr(args, key, None) for key in REDOWNLOAD_ARGS}
    for key, value in _session_values.items():
        setattr(args, key, value)


def restore_session_args():
    """Undo a redownload Yes before a run the prompt didn't start (a later
    daemon pass). Nothing to undo when the prompt never ran: the values are
    then the command line's own."""
    if _session_values is None:
        return
    args = settings.get_args()
    restore_session_values(args)
    settings.update_args(args)


def redownload_prompt(args=None):
    args = args or settings.get_args()
    answer = promptClasses.getChecklistSelection(
        message="Would you like to redownload all files",
        choices=[Choice(True, "Yes"), Choice(False, "No")],
        default=False,
    )
    if answer:
        args.force_all = True
        args.no_api_cache = True
        args.after = arrow.get("2000")
    return args
