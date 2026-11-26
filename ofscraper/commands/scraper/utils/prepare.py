import logging
import time
import re

import ofscraper.data.api.init as init
import ofscraper.managers.manager as manager
import ofscraper.utils.actions as actions
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.utils.config.data as data


log = logging.getLogger("shared")


def prepare(menu=False):
    session = manager.Manager.session.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_SEM_MAX"),
        total_timeout=of_env.getattr("API_TIMEOUT_PER_TASK"),
    )

    unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()
    if menu is True:
        actions.set_scrape_paid()
    manager.Manager.stats_manager.clear_scraper_activity_stats()
    userdata = manager.Manager.current_model_manager.prepare_scraper_activity()
    return userdata, session


def check_uniquename():
    """True when every file name template in use (file_options and each
    type_options entry but the livestream one, whose names hold the start
    time) makes names that tell files apart"""
    from ofscraper.utils.config.naming_check import LIVE_TYPE_KEYS

    formats = [data.get_fileformat()] + [
        section["file_format"]
        for name, section in data.get_type_options().items()
        if name.strip().lower() not in LIVE_TYPE_KEYS
        and isinstance(section.get("file_format"), str)
        and section["file_format"].strip()
    ]
    unique = re.compile("text|filename|post_id|postid|media_id|mediaid|custom")
    return all(unique.search(format) for format in formats)


def unique_name_warning():
    if not check_uniquename():
        log.info(
            "[red]Warning: Your generated filenames may not be unique\n \
            https://cloakedkeys.gitbook.io/ofsc/setup/getting-started/config-options/options/file-output-options/customizing-save-path[/red]      \
            "
        )
        time.sleep(of_env.getattr("LOG_DISPLAY_TIMEOUT") * 3)
