import arrow
import schedule
import logging
import time
import traceback

import ofscraper.utils.args.mutators.before as before_arg
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.logs.logger as logger
import ofscraper.managers.manager as manager
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
    jobqueue.put(manager.Manager.current_model_manager.sync_models)
    jobqueue.put(before_arg.update_before)
    for funct in functs:
        jobqueue.put(funct)
    return schedule.CancelJob
