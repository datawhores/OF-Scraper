import logging
import ofscraper.utils.settings as settings

senstiveDict = {}


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
    logging.TRACEBACK_ = level
    logging.TRACEBACK_ = level
    logging.getLoggerClass().traceback_ = logForLevel(level)
    logging.traceback_ = logToRoot(level)


def addtrace():
    level = logging.DEBUG - 5

    logging.addLevelName(level, "TRACE")
    logging.TRACE = level
    logging.TRACE = level
    logging.getLoggerClass().trace = logForLevel(level)
    logging.trace = logToRoot(level)


def getLevel(input_):
    """
    CRITICAL 50
    ERROR 40
    WARNING 30
    INFO 20
    DEBUG 10
    TRACE 5
    """
    if input_ in {"WARNING", "ERROR", "INFO", "DEBUG", "TRACE", "CRITICAL"}:
        return input_
    # for levels with different names
    return {
        "OFF": 100,
        "PROMPT": "ERROR",
        "LOW": "WARNING",
        "WARN": "WARNING",
        "NORMAL": "INFO",
    }.get(input_, 100)


def getNumber(input_):
    input_ = getLevel(input_.upper())
    if isinstance(input_, str):
        return logging.getLevelName(input_)
    return input_
