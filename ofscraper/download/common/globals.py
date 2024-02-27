import asyncio
import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor

import aioprocessing

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed

attempt = None
attempt2 = None
total_count = None
total_count2 = None
innerlog = None
localDirSet = None
req_sem = None


def reset_globals():
    # reset globals_z
    main_globals()
    set_up_contexvars()


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
    global data
    data = 0
    global total_data
    total_data = 0
    global desc
    desc = (
        "Progress: ({p_count} photos, {v_count} videos, {a_count} audios, {forced_skipped} skipped, {skipped} failed || {sumcount}/{mediacount}||{data}/{total})"
        if not read_args.retriveArgs().metadata
        else "Progress: ({p_count} photos, {v_count} videos, {a_count} audios, {forced_skipped} metadata unchanged, {skipped} failed || {sumcount}/{mediacount}||{data}/{total})"
    )
    global count_lock
    count_lock = aioprocessing.AioLock()
    global chunk_lock
    chunk_lock = aioprocessing.AioLock()

    # global
    global thread
    thread = ThreadPoolExecutor(max_workers=config_data.get_download_semaphores() * 2)
    global sem
    sem = semaphoreDelayed(config_data.get_download_semaphores())
    global cache_thread
    cache_thread = ThreadPoolExecutor()
    global dirSet
    dirSet = set()
    global mpd_sem
    mpd_sem = semaphoreDelayed(config_data.get_download_semaphores())
    global lock
    lock = asyncio.Lock()
    global maxfile_sem
    maxfile_sem = semaphoreDelayed(constants.getattr("MAXFILE_SEMAPHORE"))
    global console
    console = console_.get_shared_console()
    global localDirSet
    localDirSet = set()
    global fileHashes
    fileHashes = {}
    global req_sem
    req_sem = semaphoreDelayed(
        min(
            constants.getattr("REQ_SEMAPHORE_MULTI"),
            config_data.get_download_semaphores()
            * constants.getattr("REQ_SEMAPHORE_MULTI"),
        )
    )


def set_up_contexvars():
    global attempt
    global attempt2
    global total_count
    global total_count2
    global innerlog
    attempt = contextvars.ContextVar("attempt", default=0)
    attempt2 = contextvars.ContextVar("attempt2", default=0)
    total_count = contextvars.ContextVar("total", default=0)
    total_count2 = contextvars.ContextVar("total2", default=0)
    innerlog = contextvars.ContextVar("innerlog")


def process_split_globals(pipeCopy, logCopy):
    global pipe
    global log
    global pipe_lock
    global lock_pool
    pipe = pipeCopy
    log = logCopy
    pipe_lock = threading.Lock()
    lock_pool = ThreadPoolExecutor()
