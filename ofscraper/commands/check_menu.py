"""The check table opened from the Action Menu (#425).

"Browse and pick media (check table)" asks the usual creator questions, then
which table to open, and runs the same code as ``post_check``, ``msg_check``,
``paid_check`` or ``story_check`` for the picked creators. What the check
code changes in the settings is put back when the table closes, so the next
menu run starts from the session's own settings.
"""

import contextlib
import logging

import arrow

import ofscraper.commands.check as check
import ofscraper.managers.manager as manager
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.console as console_
import ofscraper.utils.settings as settings
from ofscraper.utils.checkers import check_auth

log = logging.getLogger("shared")

# post_check and msg_check read creators from --url, the others from --username
URL_COMMANDS = {"post_check", "msg_check"}
# post_check's default --check-area
POST_AREAS = ["Timeline", "Pinned", "Archived", "Streams"]


def run_check_table():
    check_auth(include_main_menu=True)
    models = manager.Manager.current_model_manager.select_models()
    usernames = [model.name for model in models]
    if not usernames:
        log.warning("No creators were picked, so there's no table to open")
        return
    command = prompts.check_table_prompt()
    with check_table_session(command, usernames):
        check.reset_table_data()
        check.checker()


def check_args(args, command, usernames):
    """Set args as the check command would get them from
    ``ofscraper <command> -u <usernames>``."""
    args.command = command
    if command in URL_COMMANDS:
        args.url = list(usernames)
        args.file = None
    else:
        args.check_usernames = list(usernames)
        args.file_usernames = None
    # the check commands' defaults: the cached post lists, post_check's
    # default areas, and the table sorted by number
    args.force = False
    args.check_area = list(POST_AREAS)
    args.desc = False
    # as the check commands set it (check_mode_changes)
    args.before = arrow.now().shift(days=4)
    args.before_original = None
    return args


@contextlib.contextmanager
def check_table_session(command, usernames):
    """Run the check code with the args it needs, then wait for the
    downloads sent from the table and put the session's args back."""
    saved = settings.get_args(copy=True)
    console = console_.get_shared_console()
    quiet = console.quiet
    settings.update_args(check_args(settings.get_args(), command, usernames))
    try:
        yield
    finally:
        # the table quiets the console while it's open
        console.quiet = quiet
        try:
            check.wait_for_downloads()
        finally:
            settings.update_args(saved)
