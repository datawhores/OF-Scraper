import arrow
import schedule
import logging
import time
import traceback
from functools import partial

import ofscraper.utils.args.mutators.before as before_arg
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.logs.logger as logger
import ofscraper.main.manager as manager
from ofscraper.commands.scraper.utils.jobqueue import jobqueue
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


def set_schedule(*functs):
    sleep = min(max(settings.get_settings().daemon / 5, 1), 60)
    while True:
        try:
            jobqueue.join()
            next = arrow.now().shift(minutes=settings.get_settings().daemon)
            log.debug(f"Next run at ~ {next.format('MM-DD hh:mm:ss A')}")
            schedule.every().day.at(next.format("HH:mm:ss")).do(
                schedule_helper, *functs
            )
            while len(schedule.jobs) > 0:
                schedule.run_pending()
                time.sleep(sleep)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())


def schedule_helper(*functs):
    jobqueue.put(logger.resetLogger)
    jobqueue.put(logs.printStartValues)
    jobqueue.put(
        partial(manager.Manager.model_manager.get_selected_models, rescan=True)
    )
    jobqueue.put(before_arg.update_before)
    for funct in functs:
        jobqueue.put(funct)
    jobqueue.put(manager.Manager.model_manager.reset_processed_status)
    return schedule.CancelJob
