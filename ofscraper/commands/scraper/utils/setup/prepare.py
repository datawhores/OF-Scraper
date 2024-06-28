import logging

import ofscraper.api.init as init
import ofscraper.classes.sessionmanager.ofsession as sessionManager
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.constants as constants
import ofscraper.utils.profiles.tools as profile_tools

log = logging.getLogger("shared")


def prepare(menu=False):
    session = sessionManager.OFSessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )

    download_action.unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()
    if menu is True:
        actions.set_scrape_paid()

    userdata = userselector.getselected_usernames(rescan=False)
    return userdata, session
