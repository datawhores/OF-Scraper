import logging
import time
import re

import ofscraper.data.api.init as init
import ofscraper.main.manager as manager
import ofscraper.utils.actions as actions
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.utils.config.data as data


log = logging.getLogger("shared")


def prepare(menu=False):
    session = manager.Manager.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_SEM_MAX"),
        total_timeout=of_env.getattr("API_TIMEOUT_PER_TASK"),
    )

    unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()
    if menu is True:
        actions.set_scrape_paid()

    userdata = manager.Manager.model_manager.get_selected_models(rescan=False)
    return userdata, session


def check_uniquename():
    format = data.get_fileformat()
    if re.search("text", format):
        return True
    elif re.search("filename", format):
        return True
    elif re.search("post_id", format):
        return True
    elif re.search("postid", format):
        return True
    elif re.search("media_id", format):
        return True
    elif re.search("mediaid", format):
        return True
    elif re.search("custom", format):
        return True
    return False


def unique_name_warning():
    if not check_uniquename():
        log.warning(
            "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
        )
        time.sleep(of_env.getattr("LOG_DISPLAY_TIMEOUT") * 3)
