import logging
import queue
import threading
import traceback
from collections import abc
from functools import partial

import aioprocessing

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.classes.classes as log_class
import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.utils.logs.classes.handlers.discord import (
    DiscordHandler,
    DiscordHandlerMulti,
)

from ofscraper.utils.logs.classes.handlers.file import StreamHandlerMulti
from ofscraper.utils.logs.classes.handlers.pipe import PipeHandler
from logging.handlers import QueueHandler


# processor for logging discord/log via queues, runnable by any process
def logger_other(input_, name=None, stop_count=1, event=None):
    # create a logger
    count = 0
    funct = None
    # logger is not pickable
    log = init_other_logger(name)

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
            elif message == "None" or message == None:
                count = count + 1
                continue
            elif hasattr(message, "message") and (
                message.message == "None" or message.message == None
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


# wrapper function for discord and  log, check if threads/process should star
def start_checker(func: abc.Callable):
    def inner(*args_, **kwargs):
        if settings.get_discord():
            return func(*args_, **kwargs)
        elif settings.get_log():
            return func(*args_, **kwargs)

    return inner


# processs discord/log queues via a thread
@start_checker
def start_other_thread(input_=None, count=1, name=None, other_event=None):
    input_ = input_ or log_globals.otherqueue_
    thread = threading.Thread(
        target=logger_other,
        args=(input_,),
        kwargs={"stop_count": count, "name": name, "event": other_event},
        daemon=True,
    )
    thread.start()
    return thread


# processs discord/log queues via a process
@start_checker
def start_other_process(input_=None, count=1):
    def inner(args_, date, input_=None, count=1):
        write_args.setArgs(args_)
        dates.setLogDate(date)
        input_ = input_ or log_globals.otherqueue_
        logger_other(input_, stop_count=count)

    process = None
    input_ = log_globals.otherqueue_
    process = aioprocessing.AioProcess(
        target=inner,
        args=(read_args.retriveArgs(), dates.getLogDate()),
        kwargs={"input_": input_, "count": count},
        daemon=True,
    )
    process.start() if process else None
    return process


def start_other_helper():
    if log_globals.other_log_thread:
        return
    if system.getcpu_count() >= 2:
        log_globals.other_log_thread = start_other_process()
    else:
        log_globals.other_log_thread = start_other_thread(
            other_event=log_globals.other_event
        )


# updates stream for main process
def updateOtherLoggerStream():
    if settings.get_log_level() and settings.get_log_level() != "OFF":
        dates.resetLogDateVManager()
        stream = open(
            common_paths.getlogpath(),
            encoding="utf-8",
            mode="a",
        )
        log_globals.otherqueue_.put_nowait(stream)
    if read_args.retriveArgs().discord and read_args.retriveArgs().discord != "OFF":
        temp = DiscordHandler()
        log_globals.otherqueue_.put_nowait(temp._url)


def init_other_logger(name):
    name = name or "ofscraper_other"
    log = logging.getLogger(name)
    log = add_other_handler(log)
    return log


def add_other_handler(log, clear=True):
    if clear:
        log.handlers.clear()
    format = " %(asctime)s:\[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    # # #log file
    # #discord
    cord = DiscordHandler()
    cord.setLevel(log_helpers.getLevel(read_args.retriveArgs().discord))
    cord.setFormatter(log_class.DiscordFormatter("%(message)s"))
    # console
    log.addHandler(cord)
    if settings.get_log_level() != "OFF":
        stream = open(
            common_paths.getlogpath(),
            encoding="utf-8",
            mode="a",
        )
        fh = StreamHandlerMulti(stream)
        fh.setLevel(log_helpers.getLevel(settings.get_log_level()))
        fh.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh.addFilter(log_class.NoTraceBack())
        log.addHandler(fh)
    if settings.get_log_level() in {"TRACE", "DEBUG"}:
        fh2 = StreamHandlerMulti(stream)
        fh2.setLevel(log_helpers.getLevel(settings.get_log_level()))
        fh2.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(log_class.TraceBackOnly())
        log.addHandler(fh2)
    return log


def add_other_handler_multi(log, clear=True, other_=None):
    if clear:
        log.handlers.clear()
    format = " %(asctime)s:\[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    # # #log file
    # #discord
    if not other_:
        cord = DiscordHandlerMulti()
        cord.setLevel(log_helpers.getLevel(read_args.retriveArgs().discord))
        cord.setFormatter(log_class.DiscordFormatter("%(message)s"))
        # console
        log.addHandler(cord)
        if settings.get_log_level() != "OFF":
            stream = open(
                common_paths.getlogpath(),
                encoding="utf-8",
                mode="a",
            )
            fh = StreamHandlerMulti(stream)
            fh.setLevel(log_helpers.getLevel(settings.get_log_level()))
            fh.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
            fh.addFilter(log_class.NoTraceBack())
            log.addHandler(fh)
        if settings.get_log_level() in {"TRACE", "DEBUG"}:
            fh2 = StreamHandlerMulti(stream)
            fh2.setLevel(log_helpers.getLevel(settings.get_log_level()))
            fh2.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
            fh2.addFilter(log_class.TraceBackOnly())
            log.addHandler(fh2)
    else:
        # add a handler that uses the shared queue
        discord_level = log_helpers.getNumber(settings.get_discord_level())
        file_level = log_helpers.getNumber(settings.get_log_level())
        if hasattr(other_, "get") and hasattr(other_, "put_nowait"):
            otherhandle = QueueHandler(other_)
            otherhandle.name = "other"
        elif hasattr(other_, "send"):
            otherhandle = PipeHandler(other_)
            otherhandle.name = "other"
        otherhandle.setLevel(min(file_level, discord_level))
        log.addHandler(otherhandle)
    return log
