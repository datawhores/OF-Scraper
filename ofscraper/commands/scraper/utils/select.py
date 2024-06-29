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

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.data as data
import ofscraper.utils.menu as menu
from ofscraper.commands.scraper.utils.setup.prompt import process_prompts
from ofscraper.commands.scraper.utils.setup.runner import runner

log = logging.getLogger("shared")


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
