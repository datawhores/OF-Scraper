# logs stdout logs via a shared queue

import logging
import queue
import time
import threading
import traceback
from functools import partial
from rich.logging import RichHandler

from logging.handlers import QueueHandler
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.logs.classes.classes as log_class
from ofscraper.utils.logs.classes.handlers.pipe import PipeHandler
from ofscraper.utils.logs.classes.handlers.text import TextHandler


import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.settings as settings



def logger_process(input_, name=None, stop_count=1, event=None, s=None):
    # create a logger
    # the thread must stay alive while processing pipe
    log = init_stdout_logger(name=name)
    input_ = input_ or log_globals.queue_
    count = 0
    funct = None
    if hasattr(input_, "get") and hasattr(input_, "put_nowait"):
        funct = partial(input_.get, timeout=constants.getattr("LOGGER_TIMEOUT"))
    elif hasattr(input_, "send"):
        funct = lambda: (
            input_.recv() if input_.poll(constants.getattr("LOGGER_TIMEOUT")) else False
        )
    while True:
        try:
            message = funct()
            if event and event.is_set():
                break
            elif message == "None" or message == None or message == "stop_stdout":
                count = count + 1
                continue
            elif hasattr(message, "message") and (
                message.message == "None"
                or message.message == None
                or message.message == "stop_stdout"
            ):
                count = count + 1
                continue
            elif message is False:
                raise queue.Empty
            log.handle(message)
        except queue.Empty:
            if count == stop_count:
                break
            if len(log.handlers) == 0:
                break
            if event and event.is_set():
                break
        except OSError as e:
            if str(e) == "handle is closed":
                print("handle is closed")
                return
            raise e
        except Exception as E:
            print(E)
            print(traceback.format_exc())
    for handler in log.handlers:
        handler.close()
    log.handlers.clear()


# logger for print to console
def init_stdout_logger(name=None):
    log = logging.getLogger(name or "ofscraper_stdout")
    log = add_stdout_handler(log)
    return log


def init_rich_logger(name=None):
    log = logging.getLogger(name or "ofscraper_stdout_rich")
    log = add_rich_handler(log)
    return log


def add_rich_handler(log, clear=True):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    sh = RichHandler(
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_console(),
    )
    sh.setLevel(log_helpers.getLevel(settings.get_settings().output_level))
    sh.setFormatter(log_class.SensitiveFormatter(format))
    sh.addFilter(log_class.NoTraceBack())
    log.addHandler(sh)
    if settings.get_settings().output_level in { "DEBUG"}:
        sh2 = RichHandler(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )

        sh2.setLevel(settings.get_settings().output_level)
        sh2.setFormatter(log_class.SensitiveFormatter(format))
        sh2.addFilter(log_class.TraceBackOnly())
        log.addHandler(sh2)
    return log


def add_stdout_handler(log, clear=True, rich_array=None):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    sh = RichHandler(
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_console(),
    )
    sh.setLevel(log_helpers.getLevel(settings.get_settings().output_level))
    sh.setFormatter(log_class.SensitiveFormatter(format))
    sh.addFilter(log_class.NoTraceBack())
    tx = TextHandler()
    tx.setLevel(log_helpers.getLevel(settings.get_settings().output_level))
    tx.setFormatter(log_class.LogFileFormatter(format))
    log.addHandler(sh)
    log.addHandler(tx)

    if settings.get_settings().output_level in {"DEBUG"}:
        sh2 = RichHandler(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )
        sh2.setLevel(settings.get_settings().output_level)
        sh2.setFormatter(log_class.SensitiveFormatter(format))
        sh2.addFilter(log_class.TraceBackOnly())

        log.addHandler(sh2)

    return log


def add_stdout_handler_multi(log, clear=True, main_=None):
    if clear:
        log.handlers.clear()
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    main_ = main_ or log_globals.queue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        mainhandle = QueueHandler(main_)
    elif hasattr(main_, "send"):
        mainhandle = PipeHandler(main_)
    mainhandle.name = "stdout"
    mainhandle.setLevel(log_helpers.getLevel(settings.get_settings().output_level))
    # add a handler that uses the shared queue
    log.addHandler(mainhandle)
    return log


# process main queue logs to console must be ran by main process, sharable via queues
def start_stdout_main_logthread(input_=None, name=None, count=1, event=None):
    if log_globals.main_log_thread:
        return
    thread = start_stdout_logthread_helper(input_, name, count, event)
    log_globals.main_log_thread = thread


def start_stdout_logthread(input_=None, name=None, count=1, event=None):
    start_stdout_logthread_helper(input_, name, count, event)


def start_stdout_logthread_helper(input_=None, name=None, count=1, event=None):
    input = input_ or log_globals.queue_
    main_log_thread = threading.Thread(
        target=logger_process,
        args=(input,),
        kwargs={"stop_count": count, "name": name, "event": event},
        daemon=True,
    )
    main_log_thread.start()
    return main_log_thread


def stop_stdout_main_logthread(name=None, timeout=None):
    name = name or "shared"
    if not log_globals.main_log_thread:
        return
    stop_stdout_logthread_helper(name, timeout)
    log_globals.main_log_thread = None


def stop_stdout_logthread_helper(name=None, timeout=None):
    log = logging.getLogger(name)
    log.log(100, "stop_stdout")
    log_globals.main_log_thread.join(timeout=timeout)

