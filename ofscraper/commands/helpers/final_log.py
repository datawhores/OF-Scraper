import logging
import time
import ofscraper.utils.constants as constants

def final_log(data):
    log = logging.getLogger("shared") 
    if len(data)<3:
        return
    elif constants.getattr("SHOW_RESULTS_LOG"):
        log.warning("[bold yellow]Final Results Logs[/bold yellow]")
        for record in data:
            log.warning(record)
    #give time for last long to process
    time.sleep(3)