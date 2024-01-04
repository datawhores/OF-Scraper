import copy
import io
import logging
import multiprocessing
import re
import threading
from collections import abc
from logging.handlers import QueueHandler
from threading import Event

import aioprocessing
from rich.logging import RichHandler
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_fixed

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.constants as constants
import ofscraper.utils.args as args
import ofscraper.utils.config as config_
import ofscraper.utils.console as console
import ofscraper.utils.manager as manager_
import ofscraper.utils.paths as paths
import ofscraper.utils.system as system

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


class PipeHandler(logging.Handler):
    """
    This handler sends events to a queue. Typically, it would be used together
    with a multiprocessing Queue to centralise logging to file in one process
    (in a multi-process application), so as to avoid file write contention
    between processes.

    This code is new in Python 3.2, but this class can be copy pasted into
    user code for use with earlier Python versions.
    """

    def __init__(self, pipe):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)
        self.pipe = pipe

    def prepare(self, record):
        """
        Prepare a record for queuing. The object returned by this method is
        enqueued.

        The base implementation formats the record to merge the message and
        arguments, and removes unpickleable items from the record in-place.
        Specifically, it overwrites the record's `msg` and
        `message` attributes with the merged message (obtained by
        calling the handler's `format` method), and sets the `args`,
        `exc_info` and `exc_text` attributes to None.

        You might want to override this method if you want to convert
        the record to a dict or JSON string, or send a modified copy
        of the record while leaving the original intact.
        """
        # The format operation gets traceback text into record.exc_text
        # (if there's exception data), and also returns the formatted
        # message. We can then use this to replace the original
        # msg + args, as these might be unpickleable. We also zap the
        # exc_info, exc_text and stack_info attributes, as they are no longer
        # needed and, if not None, will typically not be pickleable.
        msg = self.format(record)
        # bpo-35726: make copy of record to avoid affecting other handlers in the chain.
        record = copy.copy(record)
        record.message = msg
        record.msg = msg
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return record

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        try:
            msg = self.prepare(record)
            self.pipe[0].send(msg)
        except Exception:
            self.handleError(record)


senstiveDict = {}
process = ""


class DebugOnly(logging.Filter):
    def filter(self, record):
        if record.levelno == 10 or record.levelno == 11:
            return True
        return False


class TraceOnly(logging.Filter):
    def filter(self, record):
        if record.levelno <= 11:
            return True
        return False


class NoDebug(logging.Filter):
    def filter(self, record):
        if record.levelno <= 11:
            return False
        return True


class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.sess = sessionbuilder.sessionBuilder(
            backend="httpx",
            set_header=False,
            set_cookies=False,
            set_sign=False,
            total_timeout=10,
        )

    def emit(self, record):
        @retry(
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            stop=stop_after_attempt(constants.NUM_TRIES),
            wait=wait_fixed(8),
        )
        def inner(sess):
            with sess:
                with sess.requests(
                    url,
                    "post",
                    headers={"Content-type": "application/json"},
                    json={"content": log_entry},
                )() as r:
                    if not r.status == 204:
                        raise Exception

        log_entry = self.format(record)
        url = config_.get_discord(config_.read_config())
        log_entry = re.sub("\[bold\]|\[/bold\]", "**", log_entry)
        log_entry = f"{log_entry}\n\n"
        if url == None or url == "":
            return
        inner(self.sess)


class TextHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._widget = None

    def emit(self, record):
        # only emit after widget is set
        if self._widget == None:
            return
        log_entry = self.format(record)
        log_entry = f"{log_entry}"
        self._widget.write(log_entry)

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, widget):
        self._widget = widget


class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        s = re.sub("&Policy=[^&\"']+", "&Policy={hidden}", s)
        s = re.sub("&Signature=[^&\"']+", "&Signature={hidden}", s)
        s = re.sub("&Key-Pair-Id=[^&\"']+", "&Key-Pair-Id={hidden}", s)
        for ele in senstiveDict.items():
            s = re.sub(re.escape(str(ele[0])), str(ele[1]), s)
        return s

    def format(self, record):
        original = logging.Formatter.format(self, record)  # call parent method
        return self._filter(original)


class LogFileFormatter(SensitiveFormatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        s = SensitiveFormatter._filter(s)
        s = re.sub("\[bold\]|\[/bold\]", "", s)
        return s


def logForLevel(level):
    def inner(self, message, *args, **kwargs):
        if self.isEnabledFor(level):
            self._log(level, message, args, **kwargs)

    return inner


def logToRoot(level):
    def inner(message, *args, **kwargs):
        logging.log(level, message, *args, **kwargs)

    return inner


def addtraceback():
    level = logging.DEBUG + 1

    logging.addLevelName(level, "TRACEBACK_")
    logging.TRACEBACK = level
    setattr(logging, "TRACEBACK_", level)
    setattr(logging.getLoggerClass(), "traceback_", logForLevel(level))
    setattr(logging, "traceback_", logToRoot(level))


def addtrace():
    level = logging.DEBUG - 5

    logging.addLevelName(level, "TRACE")
    logging.TRACE = level
    setattr(logging, "TRACE", level)
    setattr(logging.getLoggerClass(), "trace", logForLevel(level))
    setattr(logging, "trace", logToRoot(level))


def updateSenstiveDict(word, replacement):
    global senstiveDict
    senstiveDict[word] = replacement


def getLevel(input):
    """
    CRITICAL 50
    ERROR 40
    WARNING 30
    INFO 20
    DEBUG 10
    TRACE 5
    """
    return {
        "OFF": 100,
        "PROMPT": "ERROR",
        "LOW": "WARNING",
        "NORMAL": "INFO",
        "DEBUG": "DEBUG",
        "TRACE": "TRACE",
    }.get(input, 100)


def getNumber(input_):
    input_ = getLevel(input_)
    if isinstance(input_, str):
        return logging.getLevelName(input_)
    return input_


# logger for print to console
def init_stdout_logger(name=None):
    log = logging.getLogger(name or "ofscraper")
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    addtraceback()
    addtrace()
    sh = RichHandler(
        rich_tracebacks=True,
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_shared_console(),
    )
    sh.setLevel(getLevel(args.getargs().output))
    sh.setFormatter(SensitiveFormatter(format))
    sh.addFilter(NoDebug())
    tx = TextHandler()
    tx.setLevel(getLevel(args.getargs().output))
    tx.setFormatter(SensitiveFormatter(format))
    log.addHandler(sh)
    log.addHandler(tx)

    if args.getargs().output in {"TRACE", "DEBUG"}:
        funct = DebugOnly if args.getargs().output == "DEBUG" else TraceOnly
        sh2 = RichHandler(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )
        sh2.setLevel(args.getargs().output)
        sh2.setFormatter(SensitiveFormatter(format))
        sh2.addFilter(funct())
        log.addHandler(sh2)

    return log


def init_other_logger(name):
    name = name or "other"
    log = logging.getLogger(name)
    format = " %(asctime)s:\[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    addtraceback()
    addtrace()
    # # #log file
    # #discord
    cord = DiscordHandler()
    cord.setLevel(getLevel(args.getargs().discord))
    cord.setFormatter(SensitiveFormatter("%(message)s"))
    # console
    log.addHandler(cord)
    if args.getargs().log != "OFF":
        stream = open(
            paths.getlogpath(),
            encoding="utf-8",
            mode="a",
        )
        fh = logging.StreamHandler(stream)
        fh.setLevel(getLevel(args.getargs().log))
        fh.setFormatter(LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh.addFilter(NoDebug())
        log.addHandler(fh)
    if args.getargs().log in {"TRACE", "DEBUG"}:
        funct = DebugOnly if args.getargs().output == "DEBUG" else TraceOnly
        fh2 = logging.StreamHandler(stream)
        fh2.setLevel(getLevel(args.getargs().log))
        fh2.setFormatter(LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(funct())
        log.addHandler(fh2)
    return log


# updates stream for main process
def updateOtherLoggerStream():
    if args.getargs().discord=="OFF" and args.getargs().log == "OFF":
        return
    args.resetGlobalDateHelper()
    stream = open(
        paths.getlogpath(),
        encoding="utf-8",
        mode="a",
    )
    otherqueue_.put_nowait(stream)


def add_widget(widget):
    [
        setattr(ele, "widget", widget)
        for ele in list(
            filter(
                lambda x: isinstance(x, TextHandler),
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
            messages = funct(timeout=constants.LOGGER_TIMEOUT)
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
def logger_other(input_,name=None, stop_count=1, event=None):
    # create a logger
    count = 0
    funct = None
    #logger is not pickable
    log= init_other_logger(name)

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
            messages = funct(timeout=constants.LOGGER_TIMEOUT)
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
def start_stdout_logthread(input_=None, name=None, count=1):
    global main_log_thread
    if main_log_thread:
        return
    input_ = input_ or queue_
    main_log_thread = threading.Thread(
        target=logger_process, args=(input_, name, count, main_event), daemon=True
    )
    main_log_thread.start()


# wrapper function for discord and  log, check if threads/process should start
def start_checker(func: abc.Callable):
    def inner(*args_, **kwargs):
        if args.getargs().discord and args.getargs().discord != "OFF":
            return func( *args_, **kwargs)
        elif args.getargs().log and args.getargs().log != "OFF":
            return func( *args_, **kwargs)

    return inner


# processs discord/log queues via a thread
@start_checker
def start_other_thread(input_=None, count=1,name=None,other_event=None):
    input_ = input_ or otherqueue_
    thread = threading.Thread(
        target=logger_other, args=(input_,), kwargs={"stop_count":count,"name":name,"event":other_event},daemon=True
    )
    thread.start()
    return thread


# processs discord/log queues via a process
@start_checker
def start_other_process( input_=None, count=1):
    def inner(args_, input_=None, count=1):
        args.changeargs(args_)
        input_ = input_ or otherqueue_
        logger_other(input_,stop_count=count)

    process = None
    input_ = otherqueue_
    process = aioprocessing.AioProcess(
        target=inner, args=(args.getargs(),),kwargs={"input_":input_,"count":count},daemon=True
    )
    process.start() if process else None
    return process


def start_other_helper():
    global other_log_thread
    if other_log_thread:
        return
    if system.getcpu_count() >= 2:
        other_log_thread= start_other_process()
    else:
       other_log_thread= start_other_thread(other_event=other_event)


# logger for putting logs into queues
def get_shared_logger(main_=None, other_=None, name=None):
    # create a logger
    logger = logging.getLogger(name or "shared")
    addtraceback()
    addtrace()
    main_ = main_ or queue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        mainhandle = QueueHandler(main_)
    elif hasattr(main_, "send"):
        mainhandle = PipeHandler(main_)
    mainhandle.setLevel(getLevel(args.getargs().output))
    # add a handler that uses the shared queue
    logger.addHandler(mainhandle)
    discord_level = getNumber(args.getargs().discord)
    file_level = getNumber(args.getargs().log)
    other_ = other_ or otherqueue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        otherhandle = QueueHandler(other_)
    elif hasattr(main_, "send"):
        otherhandle = PipeHandler(main_)
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
        main_log_thread.join(constants.FORCED_THREAD_TIMEOUT)
    elif not other_event.is_set():
        main_log_thread.join()
    main_log_thread=None
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
            other_log_thread.join(timeout=constants.FORCED_THREAD_TIMEOUT)
        else:
            other_log_thread.join(timeout=constants.FORCED_THREAD_TIMEOUT)
            if other_log_thread.is_alive():
                other_log_thread.terminate()
    other_log_thread=None


def closeQueue():
    if queue_:
        queue_.close()
        queue_.cancel_join_thread()


def discord_warning():
    if args.getargs().discord == "DEBUG":
        console.get_shared_console().print(
            "[bold red]Warning Discord with DEBUG is not recommended\nAs processing messages is much slower compared to other[/bold red]"
        )
