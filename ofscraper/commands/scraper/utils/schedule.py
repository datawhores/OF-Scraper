import arrow
import schedule
import logging
import time
import traceback
import signal

import ofscraper.utils.args.mutators.before as before_arg
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.logs.logger as logger
import ofscraper.managers.manager as manager
from ofscraper.commands.scraper.utils.jobqueue import jobqueue
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


class DaemonWakeup:
    """The signal handler only records a request; the scheduler does the work."""

    def __init__(self):
        self.state = "busy"
        self.stopped = False
        self.installed = False
        self.previous_handler = None

    def request(self, signum, frame):
        if self.state == "idle":
            self.state = "requested"

    def install(self):
        if hasattr(signal, "SIGUSR1"):
            self.previous_handler = signal.signal(signal.SIGUSR1, self.request)
            self.installed = True

    def restore(self):
        self.stopped = True
        self.state = "busy"
        if self.installed:
            signal.signal(signal.SIGUSR1, self.previous_handler)
            self.installed = False


def set_schedule(*functs, wakeup=None):
    sleep = min(max(settings.get_settings().daemon / 5, 1), 60)
    # after an error, wait the normal interval even when polling fast (#379)
    error_wait = sleep
    # Poll a plain flag: setting an Event from a Python signal handler can
    # re-enter a lock held by the interrupted main thread.
    if wakeup is not None and wakeup.installed:
        sleep = 0.1
    while wakeup is None or not wakeup.stopped:
        try:
            jobqueue.join()
            if wakeup is not None and wakeup.stopped:
                return
            next = arrow.now().shift(minutes=settings.get_settings().daemon)
            log.debug(f"Next run at ~ {next.format('MM-DD hh:mm:ss A')}")
            job = schedule.every().day.at(next.format("HH:mm:ss")).do(
                schedule_helper, *functs, wakeup=wakeup
            )
            if wakeup is not None:
                wakeup.state = "idle"
            while len(schedule.jobs) > 0 and (wakeup is None or not wakeup.stopped):
                if wakeup is not None and wakeup.state == "requested":
                    # Remove the scheduled run before queuing its replacement;
                    # a signal at the deadline must not enqueue a second pass.
                    schedule.cancel_job(job)
                    schedule_helper(*functs, wakeup=wakeup)
                    log.info("SIGUSR1 received while idle: starting the next daemon pass")
                else:
                    schedule.run_pending()
                time.sleep(sleep)
        except Exception as E:
            # the scheduler carries on (#379), after its normal interval, so
            # a repeating error neither spins nor floods the output
            log.warning(f"Daemon scheduler failed: {type(E).__name__}: {E}")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            time.sleep(error_wait)


def schedule_helper(*functs, wakeup=None):
    if wakeup is not None:
        wakeup.state = "busy"
    jobqueue.put(logger.resetLogger)
    jobqueue.put(logs.printStartValues)
    jobqueue.put(manager.Manager.current_model_manager.sync_models)
    jobqueue.put(before_arg.update_before)
    for funct in functs:
        jobqueue.put(funct)
    return schedule.CancelJob
