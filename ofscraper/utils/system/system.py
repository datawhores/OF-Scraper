import asyncio
import sys
import logging
import os
import platform

import psutil
from setproctitle import setproctitle


def getcpu_count():
    if platform.system() != "Darwin":
        return len(psutil.Process().cpu_affinity())
    else:
        return psutil.cpu_count()


def new_event_loop():
    """A new event loop: uvloop on Linux, asyncio's default elsewhere."""
    if platform.system() == "Linux":
        import uvloop

        return uvloop.new_event_loop()
    return asyncio.new_event_loop()


def set_eventloop():
    # Event loop policies are deprecated from 3.14 and removed in 3.16; there
    # loops come from new_event_loop() instead. get_event_loop() no longer
    # creates a loop on 3.14+, so run_async falls through to it.
    if platform.system() == "Linux" and sys.version_info < (3, 14):
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def get_dupe_ofscraper():
    log = logging.getLogger("shared")
    found = []
    for proc in psutil.process_iter():
        try:
            if (
                proc
                and proc.status() == "running"
                and proc.pid != os.getpid()
                and proc.name() == "OF-Scraper"
            ):
                found.append(proc)
        except psutil.NoSuchProcess:
            pass
    if found:
        log.debug(f"Duplicated Processes {found}")
    return found


def setName():
    log = logging.getLogger("shared")
    try:
        setproctitle("OF-Scraper")
    except Exception as E:
        log.debug(E)
