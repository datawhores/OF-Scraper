r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

from . import me
from rich.console import Console
console=Console()
def print_sign_status(headers):
    try:
        resp = me.scrape_user(headers)
        print('Status - \033[32mUP\033[0m')
        return "UP"
    except Exception as e:
        print('Status - \033[31mDOWN\033[0m')
        return "DOWN"
       
