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
import traceback
from functools import partial

import arrow
import schedule

import ofscraper.utils.actions as actions
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.before as before_arg
import ofscraper.utils.checkers as checkers
import ofscraper.utils.context.exit as exit
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.logs.other as other_logger
from ofscraper.commands.managers.scraper import scraperManager
import  ofscraper.runner.manager as manager


log = logging.getLogger("shared")


# Adds a function to the job queue
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
    jobqueue.put(partial(manager.Manager.model_manager.getselected_usernames, rescan=True))
    jobqueue.put(before_arg.update_before)
    for funct in functs:
        jobqueue.put(funct)
    return schedule.CancelJob


def daemon_run_helper():
    checkers.check_auth()
    global jobqueue
    jobqueue = queue.Queue()
    worker_thread = None
    scrapingManager = scraperManager()

    jobqueue.put(scrapingManager.runner)
    if read_args.retriveArgs().output == "PROMPT":
        log.info("[bold]silent-mode on[/bold]")
    log.info("[bold]Daemon mode on[/bold]")
    manager.Manager.model_manager.getselected_usernames()
    actions.select_areas()
    try:
        worker_thread = threading.Thread(
            target=set_schedule, args=[scrapingManager.runner], daemon=True
        )
        worker_thread.start()
        # Check if jobqueue has function
        while True:
            try:
                job_func = jobqueue.get()
                job_func()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
            finally:
                jobqueue.task_done()
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
