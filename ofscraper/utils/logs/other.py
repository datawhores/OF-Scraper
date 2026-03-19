import logging
import queue
from logging.handlers import QueueHandler, QueueListener

import ofscraper.utils.logs.classes.classes as log_class
import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.classes.handlers.discord import DiscordHandler

# Global listener so we can cleanly stop/flush it on shutdown
log_queue_listener = None


def add_other_handler(log, clear=True):
    global log_queue_listener

    if clear:
        log.handlers.clear()
        # If we are clearing handlers, stop the old background writer thread
        if log_queue_listener:
            log_queue_listener.stop()
            log_queue_listener = None

    format = r" %(asctime)s:\[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()

    # --- Discord Handler ---
    cord = DiscordHandler()
    cord.setLevel(log_helpers.getLevel(settings.get_settings().discord_level))
    cord.setFormatter(log_class.DiscordFormatter("%(message)s"))
    log.addHandler(cord)

    # --- File Logging (Non-Blocking Queue Setup) ---
    if settings.get_settings().log_level != "OFF":
        log_path = common_paths.getlogpath()
        file_handlers = []

        # 1. Standard Log File Handler (Writes to disk)
        fh = logging.FileHandler(log_path, encoding="utf-8", mode="a")
        fh.setLevel(log_helpers.getLevel(settings.get_settings().log_level))
        fh.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh.addFilter(log_class.NoTraceBack())
        file_handlers.append(fh)

        # 2. Traceback Log File Handler (Only if TRACE or DEBUG)
        if settings.get_settings().log_level in {"TRACE", "DEBUG"}:
            fh2 = logging.FileHandler(log_path, encoding="utf-8", mode="a")
            fh2.setLevel(log_helpers.getLevel(settings.get_settings().log_level))
            fh2.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
            fh2.addFilter(log_class.TraceBackOnly())
            file_handlers.append(fh2)

        # 3. Create the Memory Queue and attach it to the logger
        log_queue = queue.Queue()
        queue_handler = QueueHandler(log_queue)
        log.addHandler(queue_handler)

        # 4. Start the background thread that empties the queue to the files
        if not log_queue_listener:
            log_queue_listener = QueueListener(
                log_queue, *file_handlers, respect_handler_level=True
            )
            log_queue_listener.start()

    return log
