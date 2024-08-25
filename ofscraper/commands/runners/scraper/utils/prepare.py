import logging
import time

import ofscraper.data.api.init as init
import  ofscraper.runner.manager as manager2
import ofscraper.utils.actions as actions
import ofscraper.utils.constants as constants
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.classes.placeholder as placeholder
import  ofscraper.runner.manager as manager


log = logging.getLogger("shared")


def prepare(menu=False):
    session = manager2.Manager.aget_ofsession(
        sem_count=constants.getattr("API_REQ_SEM_MAX"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )

    unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()
    if menu is True:
        actions.set_scrape_paid()

    userdata = manager.Manager.model_manager.getselected_usernames(rescan=False)
    return userdata, session


def unique_name_warning():
    if not placeholder.check_uniquename():
        log.warning(
            "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
        )
        time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)
