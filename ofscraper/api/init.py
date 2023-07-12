r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

from . import me
import traceback
from rich.console import Console
import ofscraper.utils.stdout as stdout
import logging

log=logging.getLogger(__package__)


console=Console()
def print_sign_status(headers):
    with stdout.lowstdout():
        status=getstatus(headers)
        if status=="UP":
            print('Status - \033[32mUP\033[0m')
        else:
            print('Status - \033[31mDOWN\033[0m')


def getstatus(headers):
    try:
        me.scrape_user(headers)
        return "UP"
    except Exception as e:
        log.traceback(e)
        log.traceback(traceback.format_exc())
        return "DOWN"    