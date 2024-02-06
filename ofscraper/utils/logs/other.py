import io
import logging
import threading
from collections import abc

import aioprocessing

import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.classes as log_class
import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.helpers as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.system as system


# processor for logging discord/log via queues, runnable by any process
def logger_other(input_, name=None, stop_count=1, event=None):
    # create a logger
    count = 0
    funct = None
    # logger is not pickable
    log = init_other_logger(name)

    if hasattr(input_, "get") and hasattr(input_, "put_nowait"):
        funct = input_.get
        end_funct = input_.get_nowait
    elif hasattr(input_, "send"):
        funct = input_.recv
    while True:
        # consume a log message, block until one arrives
        if event and event.is_set():
            return True
        try:
            messages = funct(timeout=constants.getattr("LOGGER_TIMEOUT"))
        except:
            continue
        if not isinstance(messages, list):
            messages = [messages]
        for message in messages:
            # set close value
            if event and event.is_set():
                break
            elif message == "None":
                count = count + 1
                continue
            elif isinstance(message, io.TextIOBase):
                [
                    ele.setStream(message)
                    for ele in filter(
                        lambda x: isinstance(x, logging.StreamHandler),
                        log.handlers,
                    )
                ]
                continue
            elif message.message == "None":
                count = count + 1
                continue
            elif message.message != "None":
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


# wrapper function for discord and  log, check if threads/process should star
def start_checker(func: abc.Callable):
    def inner(*args_, **kwargs):
        if read_args.retriveArgs().discord and read_args.retriveArgs().discord != "OFF":
            return func(*args_, **kwargs)
        elif read_args.retriveArgs().log and read_args.retriveArgs().log != "OFF":
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
    if (
        read_args.retriveArgs().discord == "OFF"
        and read_args.retriveArgs().log == "OFF"
    ):
        return
    dates.resetLogDateVManager()
    stream = open(
        common_paths.getlogpath(),
        encoding="utf-8",
        mode="a",
    )
    log_globals.otherqueue_.put_nowait(stream)


def init_other_logger(name):
    name = name or "other"
    log = logging.getLogger(name)
    format = " %(asctime)s:\[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    # # #log file
    # #discord
    cord = log_class.DiscordHandler()
    cord.setLevel(log_helpers.getLevel(read_args.retriveArgs().discord))
    cord.setFormatter(log_class.SensitiveFormatter("%(message)s"))
    # console
    log.addHandler(cord)
    if read_args.retriveArgs().log != "OFF":
        stream = open(
            common_paths.getlogpath(),
            encoding="utf-8",
            mode="a",
        )
        fh = logging.StreamHandler(stream)
        fh.setLevel(log_helpers.getLevel(read_args.retriveArgs().log))
        fh.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh.addFilter(log_class.NoDebug())
        log.addHandler(fh)
    if read_args.retriveArgs().log in {"TRACE", "DEBUG"}:
        funct = (
            log_class.DebugOnly
            if read_args.retriveArgs().output == "DEBUG"
            else log_class.TraceOnly
        )
        fh2 = logging.StreamHandler(stream)
        fh2.setLevel(log_helpers.getLevel(read_args.retriveArgs().log))
        fh2.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(funct())
        log.addHandler(fh2)
    return log
