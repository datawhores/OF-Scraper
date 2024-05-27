from itertools import chain
import logging
import ofscraper.utils.constants as constants

def final_log(data):
    log = logging.getLogger("shared")

    records=list(chain.from_iterable(data))
 
    if len(records)<3:
        return
    elif constants.getattr("SHOW_RESULTS_LOG"):
        log.warning("Final Results Log")
        for record in records:
            log.warning(record)