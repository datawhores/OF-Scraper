import logging
import time
import ofscraper.utils.constants as constants

def final_log(data):
    log = logging.getLogger("shared") 
    #give space to last long
    if len(data)<3:
        return
    elif constants.getattr("SHOW_RESULTS_LOG"):
        #give time for last long to show
        time.sleep(2)
        log.warning("\n\n\n")
        log.warning("[bold yellow]Final Results Logs[/bold yellow]")
        for record in data:
                log.warning(record)
        log.warning("\n\n\n")
        #give time for last long to process
        time.sleep(3)