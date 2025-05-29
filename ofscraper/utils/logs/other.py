import logging
import ofscraper.utils.logs.classes.classes as log_class
import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.classes.handlers.discord import (
    DiscordHandler,
)

from ofscraper.utils.logs.classes.handlers.file import StreamHandlerMulti

def add_other_handler(log, clear=True):
    if clear:
        log.handlers.clear()
    format = " %(asctime)s:\[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    # # #log file
    # #discord
    cord = DiscordHandler()
    cord.setLevel(log_helpers.getLevel(settings.get_settings().discord_level))
    cord.setFormatter(log_class.DiscordFormatter("%(message)s"))
    # console
    log.addHandler(cord)
    if settings.get_settings().log_level != "OFF":
        stream = open(
            common_paths.getlogpath(),
            encoding="utf-8",
            mode="a",
        )
        fh = StreamHandlerMulti(stream)
        fh.setLevel(log_helpers.getLevel(settings.get_settings().log_level))
        fh.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh.addFilter(log_class.NoTraceBack())
        log.addHandler(fh)
    if settings.get_settings().log_level in {"TRACE", "DEBUG"}:
        fh2 = StreamHandlerMulti(stream)
        fh2.setLevel(log_helpers.getLevel(settings.get_settings().log_level))
        fh2.setFormatter(log_class.LogFileFormatter(format, "%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(log_class.TraceBackOnly())
        log.addHandler(fh2)
    return log

def getstreamHandlers(name=None):
    return [
        h for h in logging.getLogger(name or "shared").handlers
        if isinstance(h, StreamHandlerMulti)
    ]