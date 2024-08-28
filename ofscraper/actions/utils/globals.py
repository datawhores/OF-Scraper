import asyncio
import logging
import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor

import aioprocessing
import ofscraper.utils.console as console_
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.stdout import add_stdout_handler_multi
from ofscraper.utils.logs.other import add_other_handler_multi
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.dates as dates
from ofscraper.actions.utils.send.message import set_send_msg
import ofscraper.runner.manager as manager



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
    thread = ThreadPoolExecutor(max_workers=settings.get_download_sems() * 2)
    global sem
    sem = None
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


def subProcessVariableInit(
    dateDict, userList, pipeCopy, argsCopy, stdout_logqueue, file_logqueue
):
    set_up_contexvars()
    write_args.setArgs(argsCopy)
    dates.setLogDate(dateDict)
    manager.start_other_managers()
    manager.Manager.model_manager.all_subs_dict=userList
    process_split_globals(pipeCopy, stdout_logqueue, file_logqueue)
    set_send_msg()


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


def process_split_globals(pipeCopy, stdout_logqueue, file_logqueue):
    global pipe
    global pipe_lock
    global pipe_alt_lock
    global lock_pool
    global log
    main_globals()
    log = logging.getLogger("shared_process")
    log = add_stdout_handler_multi(log, clear=False, main_=stdout_logqueue)
    log = add_other_handler_multi(log, clear=False, other_=file_logqueue)
    pipe = pipeCopy
    pipe_lock = threading.Lock()
    pipe_alt_lock = threading.Lock()
    lock_pool = ThreadPoolExecutor(max_workers=1)
