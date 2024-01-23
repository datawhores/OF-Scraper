import io
import logging
import multiprocessing
import threading
from collections import abc
from logging.handlers import QueueHandler
from threading import Event

import aioprocessing
from rich.logging import RichHandler

import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.classes as log_class
import ofscraper.utils.logs.helpers as log_helpers
import ofscraper.utils.manager as manager_
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.system as system

queue_ = None
otherqueue_ = None
otherqueue2_ = None
main_event = None
other_event = None
main_log_thread = None
other_log_thread = None


def init_values():
    global queue_
    global otherqueue_
    global main_event
    global other_event
    queue_ = multiprocessing.Queue()
    otherqueue_ = manager_.get_manager().Queue()
    main_event = Event()
    other_event = Event()


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


# updates stream for main process
def updateOtherLoggerStream():
    if (
        read_args.retriveArgs().discord == "OFF"
        and read_args.retriveArgs().log == "OFF"
    ):
        return
    dates.resetLogdate()
    stream = open(
        common_paths.getlogpath(),
        encoding="utf-8",
        mode="a",
    )
    otherqueue_.put_nowait(stream)


def add_widget(widget):
    [
        setattr(ele, "widget", widget)
        for ele in list(
            filter(
                lambda x: isinstance(x, log_class.TextHandler),
                logging.getLogger("ofscraper").handlers,
            )
        )
    ]


# logs stdout logs via a shared queue
def logger_process(input_, name=None, stop_count=1, event=None):
    # create a logger
    log = init_stdout_logger(name)
    input_ = input_ or queue_
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
            while True:
                try:
                    end_funct()
                except:
                    return


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
            while True:
                try:
                    end_funct()
                except:
                    return


# process main queue logs to console must be ran by main process, sharable via queues
def start_stdout_logthread(input_=None, name=None, count=1, event=None):
    input = input_ or queue_
    if input == queue_:
        global main_log_thread
    main_log_thread = threading.Thread(
        target=logger_process,
        args=(input,),
        kwargs={"stop_count": count, "name": name, "event": event},
        daemon=True,
    )
    main_log_thread.start()
    return main_log_thread


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
    input_ = input_ or otherqueue_
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
    def inner(args_, input_=None, count=1):
        write_args.setArgs(args_)
        input_ = input_ or otherqueue_
        logger_other(input_, stop_count=count)

    process = None
    input_ = otherqueue_
    process = aioprocessing.AioProcess(
        target=inner,
        args=(read_args.retriveArgs(),),
        kwargs={"input_": input_, "count": count},
        daemon=True,
    )
    process.start() if process else None
    return process


def start_other_helper():
    global other_log_thread
    if other_log_thread:
        return
    if system.getcpu_count() >= 2:
        other_log_thread = start_other_process()
    else:
        other_log_thread = start_other_thread(other_event=other_event)


# logger for putting logs into queues
def get_shared_logger(main_=None, other_=None, name=None):
    # create a logger
    logger = logging.getLogger(name or "shared")
    log_helpers.addtraceback()
    log_helpers.addtrace()
    main_ = main_ or queue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        mainhandle = QueueHandler(main_)
    elif hasattr(main_, "send"):
        mainhandle = log_class.PipeHandler(main_)
    mainhandle.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    # add a handler that uses the shared queue
    logger.addHandler(mainhandle)
    discord_level = log_helpers.getNumber(read_args.retriveArgs().discord)
    file_level = log_helpers.getNumber(read_args.retriveArgs().log)
    other_ = other_ or otherqueue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        otherhandle = QueueHandler(other_)
    elif hasattr(main_, "send"):
        otherhandle = log_class.PipeHandler(main_)
    otherhandle.setLevel(min(file_level, discord_level))
    logger.addHandler(otherhandle)
    # log all messages, debug and up
    logger.setLevel(1)
    return logger


def start_threads():
    start_other_helper()
    start_stdout_logthread()


def gracefulClose():
    sendCloseMessage()
    stdout = logging.getLogger("ofscraper")
    stdout.debug(
        f"Main Process threads before closing log threads {threading.enumerate()}"
    )
    closeOther()
    closeMain()
    stdout.debug(
        f"Main Process threads after closing log threads {threading.enumerate()}"
    )
    closeQueue()
    stdout.debug(
        f"Main Process threads after closing cancel_join {threading.enumerate()}"
    )


def forcedClose():
    main_event.set()
    other_event.set()
    closeOther()
    closeMain()
    closeQueue()


def sendCloseMessage():
    logging.getLogger("shared").error("Finished Script")
    num_loggers = len(logging.getLogger("shared").handlers)
    if num_loggers > 0:
        logging.getLogger("shared").handlers[0].queue.put("None")
    if num_loggers > 1:
        logging.getLogger("shared").handlers[-1].queue.put("None")


def closeThreads():
    closeMain()
    closeOther()


def closeMain():
    global main_log_thread
    if not main_log_thread:
        return
    elif other_event.is_set():
        main_log_thread.join(constants.getattr("FORCED_THREAD_TIMEOUT"))
    elif not other_event.is_set():
        main_log_thread.join()
    main_log_thread = None


def closeOther():
    global other_log_thread
    if not other_log_thread:
        return
    elif not other_event.is_set():
        if isinstance(other_log_thread, threading.Thread):
            other_log_thread.join()
        else:
            other_log_thread.join()
    elif other_event.is_set():
        if isinstance(other_log_thread, threading.Thread):
            other_log_thread.join(timeout=constants.getattr("FORCED_THREAD_TIMEOUT"))
        else:
            other_log_thread.join(timeout=constants.getattr("FORCED_THREAD_TIMEOUT"))
            if other_log_thread.is_alive():
                other_log_thread.terminate()
    other_log_thread = None


def closeQueue():
    if queue_:
        queue_.close()
        queue_.cancel_join_thread()
