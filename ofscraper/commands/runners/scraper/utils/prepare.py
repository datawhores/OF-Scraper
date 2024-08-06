import logging
import time

import ofscraper.data.api.init as init
import ofscraper.classes.sessionmanager.ofsession as sessionManager
import ofscraper.data.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.constants as constants
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.classes.placeholder as placeholder


log = logging.getLogger("shared")


def prepare(menu=False):
    session = sessionManager.OFSessionManager(
        sem_count=constants.getattr("API_REQ_SEM_MAX"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )

    unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()
    if menu is True:
        actions.set_scrape_paid()

    userdata = userselector.getselected_usernames(rescan=False)
    return userdata, session


def unique_name_warning():
    if not placeholder.check_uniquename():
        log.warning(
            "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
        )
        time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)