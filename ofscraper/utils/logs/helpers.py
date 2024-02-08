import logging

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


def getSenstiveDict():
    global senstiveDict
    return senstiveDict


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
