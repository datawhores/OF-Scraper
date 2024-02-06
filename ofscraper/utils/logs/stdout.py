# logs stdout logs via a shared queue

import io
import logging
import threading
from collections import abc
from logging.handlers import QueueHandler

import aioprocessing
from rich.logging import RichHandler

import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.classes as log_class
import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.helpers as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.system as system


def logger_process(input_, name=None, stop_count=1, event=None):
    # create a logger
    log = init_stdout_logger(name)
    input_ = input_ or log_globals.queue_
    count = 0
    funct = None
    if hasattr(input_, "get") and hasattr(input_, "put_nowait"):
        funct = input_.get
        end_funct = input_.get_nowait
    elif hasattr(input_, "send"):
        funct = input_.recv
    while True:
        # consume a log message, block until one arrives
        if event and event.is_set():
            return
        try:
            messages = funct(timeout=constants.getattr("LOGGER_TIMEOUT"))
        except:
            continue
        if not isinstance(messages, list):
            messages = [messages]
        for message in messages:
            # check for shutdown
            if event and event.is_set():
                break
            if message == "None":
                count = count + 1
                continue
            if message.message == "None":
                count = count + 1
                continue
            if message.message != "None":
                # log the message
                log.handle(message)
        if count == stop_count:
            break
    while True:
        try:
            end_funct()
        except:
            break
    log.handlers.clear()


# logger for print to console
def init_stdout_logger(name=None):
    log = logging.getLogger(name or "ofscraper")
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    sh = RichHandler(
        rich_tracebacks=True,
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_shared_console(),
    )
    sh.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    sh.setFormatter(log_class.SensitiveFormatter(format))
    sh.addFilter(log_class.NoDebug())
    tx = log_class.TextHandler()
    tx.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    tx.setFormatter(log_class.SensitiveFormatter(format))
    log.addHandler(sh)
    log.addHandler(tx)

    if read_args.retriveArgs().output in {"TRACE", "DEBUG"}:
        funct = (
            log_class.DebugOnly
            if read_args.retriveArgs().output == "DEBUG"
            else log_class.TraceOnly
        )
        sh2 = RichHandler(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )
        sh2.setLevel(read_args.retriveArgs().output)
        sh2.setFormatter(log_class.SensitiveFormatter(format))
        sh2.addFilter(funct())
        log.addHandler(sh2)

    return log


# process main queue logs to console must be ran by main process, sharable via queues
def start_stdout_logthread(input_=None, name=None, count=1, event=None):
    input = input_ or log_globals.queue_
    if input == log_globals.queue_:
        global main_log_thread
    main_log_thread = threading.Thread(
        target=logger_process,
        args=(input,),
        kwargs={"stop_count": count, "name": name, "event": event},
        daemon=True,
    )
    main_log_thread.start()
    return main_log_thread
