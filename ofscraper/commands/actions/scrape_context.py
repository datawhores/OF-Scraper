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
import timeit
from contextlib import contextmanager

import arrow

log = logging.getLogger("shared")


@contextmanager
def scrape_context_manager():
    # reset stream if needed
    # Before yield as the enter method
    start = timeit.default_timer()
    log.warning(
        """
==============================                            
[bold] starting script [/bold]
==============================
"""
    )
    yield
    end = timeit.default_timer()
    log.warning(
        f"""
===========================
[bold] Script Finished [/bold]
Run Time:  [bold]{str(arrow.get(end)-arrow.get(start)).split(".")[0]}[/bold]
===========================
"""
    )
