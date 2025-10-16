import logging


def gracefulClose():
    sendCloseMessage()


def sendCloseMessage():
    logging.getLogger("shared").error("Finished Script")


def clearHandlers():
    logging.getLogger("shared").handlers.clear()
    logging.getLogger("ofscraper_stdout").handlers.clear()
