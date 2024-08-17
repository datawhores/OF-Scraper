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
from ofscraper.commands.runners.scraper.utils.print import print_start
from ofscraper.commands.runners.scraper.utils.select import process_selected_areas
from ofscraper.commands.runners.scraper.utils.prompt import process_prompts

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
