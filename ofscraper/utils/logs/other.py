import logging
import queue
from logging.handlers import QueueHandler, QueueListener

import ofscraper.utils.logs.classes.classes as log_class
import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.classes.handlers.discord import DiscordHandler

# --- ONE GLOBAL QUEUE FOR ALL LOGGERS ---
global_log_queue = queue.Queue()
log_queue_listener = None


def add_other_handler(log, clear=True):
    global log_queue_listener
    global global_log_queue

    if clear:
        log.handlers.clear()

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
        # All loggers now push to the exact same global queue
        queue_handler = QueueHandler(global_log_queue)
        log.addHandler(queue_handler)

        # Only start the background listener if it isn't already running
        if not log_queue_listener:
            log_path = common_paths.getlogpath()
            file_handlers = []

            # Standard Log File Handler (Writes to disk)
            fh = logging.FileHandler(log_path, encoding="utf-8", mode="a")
            fh.setLevel(log_helpers.getLevel(settings.get_settings().log_level))
            fh.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
            file_handlers.append(fh)

            log_queue_listener = QueueListener(
                global_log_queue, *file_handlers, respect_handler_level=True
            )
            log_queue_listener.start()

    return log