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
        other_logs.log_queue_listener.stop()
        other_logs.log_queue_listener = None

    # 2. CLEAR THE HANDLERS:
    # Now that the files are safely written, we can detach the loggers.
    logging.getLogger("shared").handlers.clear()
    logging.getLogger("ofscraper_stdout").handlers.clear()
    logging.getLogger("ofscraper_download").handlers.clear()


def sendCloseMessage():
    logging.getLogger("shared").error("Finished Script")
