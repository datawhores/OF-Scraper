import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

import aioprocessing
import ofscraper.utils.console as console_
import ofscraper.utils.settings as settings
import ofscraper.utils.logs.logger as logger


attempt = None
attempt2 = None
total_count = None
total_count2 = None
innerlog = None
localDirSet = None
log = None

# count
photo_count = 0
video_count = 0
audio_count = 0
skipped = 0
forced_skipped = 0
total_bytes_downloaded = 0


def main_globals():
    global total_bytes_downloaded
    total_bytes_downloaded = 0
    global total_bytes
    total_bytes = 0
    global photo_count
    photo_count = 0
    global video_count
    video_count = 0
    global audio_count
    audio_count = 0
    global skipped
    skipped = 0
    global forced_skipped
    forced_skipped = 0
    global count_lock
    count_lock = aioprocessing.AioLock()
    global chunk_lock
    chunk_lock = aioprocessing.AioLock()

    # global
    global thread
    thread = ThreadPoolExecutor(max_workers=settings.get_settings().download_sems * 2)
    global sem
    sem=asyncio.Semaphore(settings.get_settings().download_sems)
    global dirSet
    dirSet = set()
    global lock
    lock = asyncio.Lock()
    global console
    console = console_.get_shared_console()
    global localDirSet
    localDirSet = set()
    global fileHashes
    fileHashes = {}
    global log
    log = logger.get_shared_logger(name="ofscraper_download")


def mainProcessVariableInit():
    set_up_contexvars()
    main_globals()


def set_up_contexvars():
    global attempt
    global attempt2
    global total_count
    global total_count2
    attempt = contextvars.ContextVar("attempt", default=0)
    attempt2 = contextvars.ContextVar("attempt2", default=0)
    total_count = contextvars.ContextVar("total", default=0)
    total_count2 = contextvars.ContextVar("total2", default=0)
