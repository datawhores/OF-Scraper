import arrow
import schedule
import logging
import time
import traceback
from functools import partial

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.before as before_arg
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.logs.other as other_logger
import ofscraper.main.manager as manager
from ofscraper.commands.scraper.utils.jobqueue import jobqueue

log = logging.getLogger("shared")


def set_schedule(*functs):
    sleep = min(max(read_args.retriveArgs().daemon / 5, 1), 60)
    while True:
        try:
            jobqueue.join()
            next = arrow.now().shift(minutes=read_args.retriveArgs().daemon)
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
    jobqueue.put(other_logger.updateOtherLoggerStream)
    jobqueue.put(logs.printStartValues)
    jobqueue.put(
        partial(manager.Manager.model_manager.getselected_usernames, rescan=True)
    )
    jobqueue.put(before_arg.update_before)
    for funct in functs:
        jobqueue.put(funct)
    return schedule.CancelJob