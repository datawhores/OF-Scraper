import logging
from logging.handlers import QueueHandler

import ofscraper.utils.args.read as read_args
import ofscraper.utils.logs.classes as log_class
import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.helpers as log_helpers
import ofscraper.utils.logs.other as log_others
import ofscraper.utils.logs.stdout as log_stdout


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


# logger for putting logs into queues
def get_shared_logger(main_=None, other_=None, name=None):
    # create a logger
    logger = logging.getLogger(name or "shared")
    log_helpers.addtraceback()
    log_helpers.addtrace()
    main_ = main_ or log_globals.queue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        mainhandle = QueueHandler(main_)
    elif hasattr(main_, "send"):
        mainhandle = log_class.PipeHandler(main_)
    mainhandle.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    # add a handler that uses the shared queue
    logger.addHandler(mainhandle)
    discord_level = log_helpers.getNumber(read_args.retriveArgs().discord)
    file_level = log_helpers.getNumber(read_args.retriveArgs().log)
    other_ = other_ or log_globals.otherqueue_
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
    log_others.start_other_helper()
    log_stdout.start_stdout_logthread()
