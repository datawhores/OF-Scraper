r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import logging
import traceback

from rich.console import Console

import ofscraper.utils.stdout as stdout

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
