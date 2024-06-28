r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      f
"""

import logging
import traceback

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.context.exit as exit
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.run as run
import ofscraper.utils.system.network as network
from ofscraper.commands.scraper.helpers.print import print_start
from ofscraper.commands.scraper.helpers.prompt import process_prompts
import logging
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.helpers.shared import run_action_bool

from ofscraper.commands.helpers.final_log import final_log
from ofscraper.commands.scraper.helpers.scrape_context import scrape_context_manager
from ofscraper.utils.checkers import check_auth
from ofscraper.commands.scraper.userfirst import process_users_actions_user_first
from ofscraper.commands.scraper.normal import process_users_actions_normal
from ofscraper.commands.scraper.helpers.prepare import prepare

import logging

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.data as data
from ofscraper.__version__ import __version__
import ofscraper.utils.menu as menu
from ofscraper.commands.scraper.helpers.prompt import process_prompts
import ofscraper.api.init as init
import ofscraper.classes.sessionmanager.ofsession as sessionManager
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.constants as constants
import ofscraper.utils.profiles.tools as profile_tools
log = logging.getLogger("shared")


log = logging.getLogger("shared")


def daemon_process():
    run.daemon_run_helper()
    pass



def main():
    try:
        print_start()
        paths.temp_cleanup()
        paths.cleanDB()
        network.check_cdm()

        scrapper()
        paths.temp_cleanup()
        paths.cleanDB()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.temp_cleanup()
                paths.cleanDB()
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.temp_cleanup()
                paths.cleanDB()
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E


def scrapper():
    global selectedusers
    selectedusers = None
    args = read_args.retriveArgs()
    if args.daemon:
        if len(args.action) == 0 and not args.scrape_paid:
            prompts.action_prompt()
        daemon_process()
    elif len(args.action) > 0 or args.scrape_paid:
        process_selected_areas()
    elif len(args.action) == 0:
        process_prompts()

def process_selected_areas():
    log.debug("[bold deep_sky_blue2] Running Action Mode [/bold deep_sky_blue2]")
    runner()
    while True:
        if not data.get_InfiniteLoop() or prompts.continue_prompt() == "No":
            break
        action = prompts.action_prompt()
        if action == "main":
            process_prompts()
            break
        elif action == "quit":
            break
        else:
            menu.get_count() > 0 and menu.reset_menu_helper()
            runner()
            menu.update_count()       

@exit.exit_wrapper
def runner(menu=False):
    check_auth()
    with scrape_context_manager(
    ):
        normal_data=[]
        user_first_data=[
        ]
        scrape_paid_data=[]
        with progress_utils.setup_activity_group_live(setup=True,revert=False,stop=True):
            if read_args.retriveArgs().scrape_paid:
                scrape_paid_data=download_action.scrape_paid_all()

            if not run_action_bool():
                pass

            elif read_args.retriveArgs().users_first:
                userdata, session = prepare(menu=menu)
                user_first_data=process_users_actions_user_first(userdata, session)
            else:
                userdata, session = prepare()
                normal_data=process_users_actions_normal(userdata, session)
        final_log(normal_data+scrape_paid_data+user_first_data)

def prepare(menu=False):
    session = sessionManager.OFSessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )

    download_action.unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()
    if menu==True:
        actions.set_scrape_paid()


    userdata = userselector.getselected_usernames(rescan=False)
    return userdata, session