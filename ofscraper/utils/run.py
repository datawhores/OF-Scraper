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
import queue
import threading
import time
from contextlib import contextmanager
from functools import partial

import schedule

import ofscraper.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.args.read as read_args
import ofscraper.utils.context.exit as exit
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.logs as logs

log = logging.getLogger("shared")


# Adds a function to the job queue
def set_schedule(*functs):
    schedule.every(read_args.retriveArgs().daemon).minutes.do(schedule_helper, functs)
    while len(schedule.jobs) > 0:
        schedule.run_pending()
        time.sleep(30)


def schedule_helper(functs):
    jobqueue.put(logger.start_threads)
    jobqueue.put(logger.updateOtherLoggerStream)
    jobqueue.put(logs.printStartValues)
    jobqueue.put(partial(userselector.getselected_usernames, rescan=True))
    for funct in functs:
        jobqueue.put(funct)
    jobqueue.put(logger.closeThreads)


def daemon_run_helper(*functs):
    global jobqueue
    jobqueue = queue.Queue()
    worker_thread = None
    [jobqueue.put(funct) for funct in functs]
    if read_args.retriveArgs().output == "PROMPT":
        log.info(f"[bold]silent-mode on[/bold]")
    log.info(f"[bold]Daemon mode on[/bold]")
    userselector.getselected_usernames(rescan=True, reset=True)
    actions.select_areas()
    try:
        worker_thread = threading.Thread(
            target=set_schedule, args=[*functs], daemon=True
        )
        worker_thread.start()
        # Check if jobqueue has function
        while True:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
            log.debug(list(map(lambda x: x, schedule.jobs)))
    except KeyboardInterrupt as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise E
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
            raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise E


def run_helper(*functs):
    # run each function once
    global jobqueue
    jobqueue = queue.Queue()
    [jobqueue.put(funct) for funct in functs]
    if read_args.retriveArgs().output == "PROMPT":
        log.info(f"[bold]silent-mode on[/bold]")
    try:
        for _ in functs:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
        dates.resetLogdate()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E
