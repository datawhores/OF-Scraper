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

import logging

import ofscraper.api.init as init
import ofscraper.classes.sessionmanager.ofsession as sessionManager
import ofscraper.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.commands.metadata.normal import process_users_metadata_normal
from ofscraper.commands.metadata.paid import metadata_paid_all
from ofscraper.commands.metadata.userfirst import metadata_user_first
from ofscraper.commands.scraper.utils.scrape_context import scrape_context_manager
from ofscraper.commands.utils.final_log import final_log
from ofscraper.commands.utils.shared import run_metadata_bool
from ofscraper.utils.checkers import check_auth

log = logging.getLogger("shared")


def metadata():
    check_auth()
    with progress_utils.setup_activity_progress_live(
        revert=True, stop=True, setup=True
    ):
        scrape_paid_data = []
        userfirst_data = []
        normal_data = []
        if read_args.retriveArgs().scrape_paid:
            scrape_paid_data = metadata_paid_all()
        if not run_metadata_bool():
            pass

        elif not read_args.retriveArgs().users_first:
            userdata, session = prepare()
            normal_data = process_users_metadata_normal(userdata, session)
        else:
            userdata, session = prepare()
            userfirst_data = metadata_user_first(userdata, session)
    final_log(normal_data + scrape_paid_data + userfirst_data)


def process_selected_areas():
    log.debug("[bold deep_sky_blue2] Running Metadata Mode [/bold deep_sky_blue2]")
    progress_updater.update_activity_task(description="Running Metadata Mode")
    with scrape_context_manager():
        with progress_utils.setup_activity_group_live(revert=True):
            metadata()


def prepare():
    profile_tools.print_current_profile()
    actions.select_areas()
    init.print_sign_status()
    userdata = userselector.getselected_usernames(rescan=False)
    session = sessionManager.OFSessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )
    return userdata, session
