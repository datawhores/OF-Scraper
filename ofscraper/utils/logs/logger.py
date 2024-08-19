import logging

import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.stdout import add_stdout_handler, start_flush_main_thread
from ofscraper.utils.logs.other import add_other_handler
from ofscraper.utils.logs.classes.handlers.text import TextHandler


def add_widget(widget):
    [
        setattr(ele, "widget", widget)
        for ele in list(
            filter(
                lambda x: isinstance(x, TextHandler),
                logging.getLogger("shared").handlers,
            )
        )
    ]


# logger for putting logs into queues
def get_shared_logger(name=None):
    # create a logger
    logger = logging.getLogger(name or "shared")
    logger_other = logging.getLogger(f"{name}_other" if name else "shared_other")
    logger.handlers.clear()
    log_helpers.addtraceback()
    log_helpers.addtrace()
    add_stdout_handler(logger, clear=False)
    add_other_handler(logger, clear=False)
    add_other_handler(logger_other, clear=False)
    if settings.get_output_level() == "LOW":
        add_stdout_handler(logger_other, clear=False)
    # log all messages, debug and up
    logger.setLevel(1)
    logger_other.setLevel(1)
    return logger


def start_threads():
    start_flush_main_thread()
