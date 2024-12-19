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
import time
import itertools

import ofscraper.utils.constants as constants
import ofscraper.utils.logs.stdout as stdout_logs


def final_log(data):
    log = logging.getLogger("shared")
    stdout_logs.restart_flush_main_thread(threads=1)
    if constants.getattr("SHOW_RESULTS_LOG"):
        # give time for last long to show
        time.sleep(2)
        log.warning("\n\n\n")
        log.warning("[bold yellow]Final Results Logs[/bold yellow]")
        flattened_list = []
        [
            (
                flattened_list.extend(ele)
                if isinstance(ele, list)
                else flattened_list.append(ele)
            )
            for ele in data
        ]
        for record in flattened_list:
            if record == None:
                continue
            log.warning(record)
        log.warning("\n\n\n")
        # give time for last long to process
        time.sleep(3)
