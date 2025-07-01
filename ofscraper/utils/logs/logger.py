import logging

import ofscraper.utils.logs.utils.level as log_helpers
from ofscraper.utils.logs.stdout import add_stdout_handler
from ofscraper.utils.logs.other import add_other_handler,getstreamHandlers
from ofscraper.utils.logs.classes.handlers.text import TextHandler
import ofscraper.utils.dates as dates


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

def get_shared_logger(name=None):
    # create a logger
    logger = logging.getLogger(name or "shared")
    clearHandlers(name)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    add_stdout_handler(logger, clear=False)
    add_other_handler(logger, clear=False)
    logger.setLevel(1)
    #don't propate to root
    logger.propagate=False
    return logger

def clearHandlers(name=None):
    log=logging.getLogger(name or "shared")
    for handler in log.handlers[:]:  # Iterate over a copy of the list
        try:
            log.removeHandler(handler)
            handler.close()  # Release resources (critical for file handlers)
        except Exception as e:
            # Basic error handling (optional)
            print(f"Error closing handler: {str(e)}")
    log=log.parent


def resetLogger():
    dates.resetLogDateVManager()
    get_shared_logger()

def flushlogs():
    for handler in getstreamHandlers():
        handler.flush()

