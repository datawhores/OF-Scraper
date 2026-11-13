import logging


def gracefulClose():
    """
    Called when the script is shutting down.
    """
    sendCloseMessage()

    import ofscraper.utils.logs.other as other_logs

    # 1. STOP THE LISTENER FIRST:
    # This forces the background thread to flush everything in the queue to the hard drive.
    if hasattr(other_logs, "log_queue_listener") and other_logs.log_queue_listener:
        listener = other_logs.log_queue_listener
        listener.stop()
        # stop() flushes but leaves the handlers (and the log file) open
        for handler in listener.handlers:
            handler.close()
        other_logs.log_queue_listener = None

    # 2. CLEAR THE HANDLERS:
    # Now that the files are safely written, we can detach the loggers.
    for name in ("shared", "ofscraper_stdout", "ofscraper_download"):
        logger = logging.getLogger(name)
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()


def sendCloseMessage():
    logging.getLogger("shared").error("Finished Script")
