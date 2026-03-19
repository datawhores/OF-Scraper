import asyncio
import re
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


def set_eventloop():
    plat = platform.system()
    if plat == "Linux":
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