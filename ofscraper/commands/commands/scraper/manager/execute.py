import logging

import ofscraper.commands.commands.scraper.actions.download as download_action
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.commands.scraper.runner.normal.normal import process_users_actions_normal
from ofscraper.commands.commands.scraper.runner.userfirst.userfirst import process_users_actions_user_first
from ofscraper.commands.utils.scrape_context import scrape_context_manager
from ofscraper.commands.commands.scraper.utils.setup.prepare import prepare
from ofscraper.commands.utils.run_action import run_action_bool
from ofscraper.utils.checkers import check_auth
from ofscraper.commands.final.final import final

log = logging.getLogger("shared")


@exit.exit_wrapper
def runner(menu=False):
    check_auth()
    with scrape_context_manager():
        normal_data = []
        user_first_data = []
        scrape_paid_data = []
        with progress_utils.setup_activity_group_live(
            setup=True, revert=False, stop=True
        ):
            if read_args.retriveArgs().scrape_paid:
                scrape_paid_data = download_action.scrape_paid_all()

            if not run_action_bool():
                pass

            elif read_args.retriveArgs().users_first:
                userdata, session = prepare(menu=menu)
                user_first_data = process_users_actions_user_first(userdata, session)
            else:
                userdata, session = prepare()
                normal_data = process_users_actions_normal(userdata, session)
        final(normal_data , scrape_paid_data ,user_first_data,userdata)
