import asyncio
import random
import re
import logging
import multiprocessing
import os
import platform
import sys

import multiprocess
import psutil
from setproctitle import setproctitle


def is_frozen():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return True
    else:
        return False


def get_parent_process():
    return multiprocess.parent_process() is None


def get_parent():
    return get_parent_process() or "pytest" not in sys.modules


def getcpu_count():
    if platform.system() != "Darwin":
        return len(psutil.Process().cpu_affinity())
    else:
        return psutil.cpu_count()


def getOpenFiles(unique=True):
    match = set()
    out = []
    for proc in psutil.process_iter():
        for ele in proc.open_files():
            if not unique:
                out.append(ele)
            elif ele.fd not in match:
                out.append(ele)
                match.add(ele.fd)
    return out


def set_mulitproc_start_type():
    plat = platform.system()
    if is_frozen():
        f_method = "spawn"
        multiprocess.set_start_method(f_method)
        multiprocessing.set_start_method(f_method)
    elif plat == "Darwin":
        d_method = "spawn"
        multiprocess.set_start_method(d_method)
        multiprocessing.set_start_method(d_method)
    elif plat == "Windows":
        w_method = "spawn"
        multiprocess.set_start_method(w_method)
        multiprocessing.set_start_method(w_method)
    else:
        o_method = "forkserver"
        multiprocess.set_start_method(o_method)
        multiprocessing.set_start_method(o_method)
    # additional for mac
    if plat == "Darwin":
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        os.environ["no_proxy"] = "*"


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
    log.debug(f"Duplicated Processes {found}")
    return found


def get_all_ofscrapers_processes():
    found = []
    for proc in psutil.process_iter():
        try:
            if proc and (re.search("^OF-Scraper", proc.name())):
                found.append(proc)
        except psutil.NoSuchProcess:
            pass
    return found


def setName():
    log = logging.getLogger("shared")
    try:
        setproctitle("OF-Scraper")
    except Exception as E:
        log.debug(E)


def setNameAlt():
    log = logging.getLogger("shared")
    try:
        setproctitle("OF-Scraper_")
    except Exception as E:
        log.debug(E)


def getName():
    return psutil.Process().name()
