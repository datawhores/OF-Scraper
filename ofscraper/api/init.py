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
import traceback

from rich.console import Console

import ofscraper.utils.context.stdout as stdout

from . import me

log = logging.getLogger("shared")

console = Console()


def print_sign_status():
    with stdout.lowstdout():
        status = getstatus()
        if status == "UP":
            print("Status - \033[32mUP\033[0m")
        else:
            print("Status - \033[31mDOWN\033[0m")


def getstatus():
    try:
        me.scrape_user()
        return "UP"
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        return "DOWN"
