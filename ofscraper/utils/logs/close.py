import logging
import threading

import ofscraper.utils.constants as constants
import ofscraper.utils.logs.globals as log_globals


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
    log_globals.main_event.set()
    log_globals.other_event.set()
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
    elif log_globals.other_event.is_set():
        main_log_thread.join(constants.getattr("FORCED_THREAD_TIMEOUT"))
    elif not log_globals.other_event.is_set():
        main_log_thread.join()
    main_log_thread = None


def closeOther():
    global other_log_thread
    if not other_log_thread:
        return
    elif not log_globals.other_event.is_set():
        if isinstance(other_log_thread, threading.Thread):
            other_log_thread.join()
        else:
            other_log_thread.join()
    elif log_globals.other_event.is_set():
        if isinstance(other_log_thread, threading.Thread):
            other_log_thread.join(timeout=constants.getattr("FORCED_THREAD_TIMEOUT"))
        else:
            other_log_thread.join(timeout=constants.getattr("FORCED_THREAD_TIMEOUT"))
            if other_log_thread.is_alive():
                other_log_thread.terminate()
    other_log_thread = None


def closeQueue():
    if log_globals.queue_:
        log_globals.queue_.close()
        log_globals.queue_.cancel_join_thread()
