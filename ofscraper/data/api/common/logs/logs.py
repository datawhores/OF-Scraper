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

import ofscraper.data.api.common.logs.strings as common_logs
from ofscraper.utils.logs.utils.trace import is_trace


log = logging.getLogger("shared")


sem = None


def trace_progress_log(area, data, offset=None):
    if not is_trace():
        return
    log.trace(f"{common_logs.PROGRESS_RAW_TITLE.format(area)}")
    for count, ele in enumerate(data):
        if offset != None and offset != False:
            log.trace(common_logs.PROGRESS_RAW_OFFSET.format(offset, area, count, ele))
        log.trace(common_logs.PROGRESS_RAW.format(area, count, ele))


def trace_log_raw(title, responseArray, final_count=None):
    if not is_trace():
        return
    if not final_count:
        log.trace(title)
    else:
        log.trace(common_logs.FINAL_COUNT.format(title))
    for count, ele in enumerate(responseArray):
        log.trace(f"[{title}]  current item count:{count} data: {ele}")
