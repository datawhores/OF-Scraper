import logging

import ofscraper.utils.constants as constants
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")


def trace_log_user(responseArray, title_str):
    if not is_trace():
        return
    log.trace({title_str.strip().capitalize()})
    for count,ele in enumerate(responseArray):
        log.trace(f"[userdata raw] count: {count} data:{ele})
