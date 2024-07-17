import asyncio
import logging
import logging.handlers
import os
import platform
import random
import threading
import time
import traceback
from functools import partial

import aioprocessing
import more_itertools
from aioprocessing import AioPipe

import ofscraper.download.utils.globals as common_globals
import ofscraper.models.selector as selector
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.context.exit as exit
import ofscraper.utils.dates as dates
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater

import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
import ofscraper.utils.system.priority as priority

from ofscraper.classes.sessionmanager.download import download_session
from ofscraper.download.alt_downloadbatch import alt_download
from ofscraper.download.main_downloadbatch import main_download
from ofscraper.download.utils.globals import subProcessVariableInit
from ofscraper.download.utils.log import (
    final_log,
    final_log_text,
    log_download_progress,
    set_media_log,
)
from ofscraper.download.utils.log import get_medialog

from ofscraper.download.utils.metadata import metadata
from ofscraper.download.utils.paths.paths import addGlobalDir, setDirectoriesDate
from ofscraper.download.utils.progress.progress import convert_num_bytes
from ofscraper.download.utils.send.message import send_msg
from ofscraper.download.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.logs.other as other_logs

from ofscraper.utils.system.speed import add_pids_to_download_obj
from ofscraper.download.utils.buffer import download_log_clear_helper


platform_name = platform.system()



def process_dicts(username, model_id, filtered_medialist):
    metadata_md = read_args.retriveArgs().metadata
    log = logging.getLogger("shared")
    live = (
        partial(progress_utils.setup_download_progress_live, multi=True)
        if not metadata_md
        else partial(progress_utils.setup_metadata_progress_live)
    )
    try:
        common_globals.main_globals()
        download_log_clear_helper()
        with live():
            if not read_args.retriveArgs().item_sort:
                random.shuffle(filtered_medialist)

            mediasplits = get_mediasplits(filtered_medialist)
            num_proc = len(mediasplits)
            log.debug(f"Number of download threads: {num_proc}")
            connect_tuples = [AioPipe() for _ in range(num_proc)]
            stdout_logqueues = [AioPipe() for _ in range(num_proc)]
    
            #start stdout/main queues consumers
            log_threads=[]
            for i in range(num_proc):
                thread=stdout_logs.start_stdout_logthread(
                input_=stdout_logqueues[i][0],
                name=f"ofscraper_{model_id}_{i+1}",
                count=1,
                )
                log_threads.append(thread)


            processes = [
                aioprocessing.AioProcess(
                    target=process_dict_starter,
                    args=(
                        username,
                        model_id,
                        mediasplits[i],
                        stdout_logqueues[i][1],
                        connect_tuples[i][1],
                        dates.getLogDate(),
                        selector.get_ALL_SUBS_DICT(),
                        read_args.retriveArgs(),
                    ),

                )
                for i in range(num_proc)
            ]
            [process.start() for process in processes]
            add_pids_to_download_obj(map(lambda x: x.pid, processes))

            task1 = progress_updater.add_download_task(
                common_globals.desc.format(
                    p_count=0,
                    v_count=0,
                    a_count=0,
                    skipped=0,
                    mediacount=len(filtered_medialist),
                    forced_skipped=0,
                    sumcount=0,
                    total_bytes_download=0,
                    total_bytes=0,
                ),
                total=len(filtered_medialist),
                visible=True,
            )

            # for reading completed downloads
            queue_threads = [
                threading.Thread(
                    target=queue_process,
                    args=(
                        connect_tuples[i][0],
                        task1,
                        len(filtered_medialist),
                    ),
                    daemon=True,
                )
                for i in range(num_proc)
            ]
            [thread.start() for thread in queue_threads]
            log.debug(f"Initial Queue Threads: {queue_threads}")
            log.debug(f"Number of initial Queue Threads: {len(queue_threads)}")
            while True:
                newqueue_threads = list(
                    filter(lambda x: x and x.is_alive(), queue_threads)
                )
                if len(newqueue_threads) != len(queue_threads):
                    log.debug(f"Remaining Queue Threads: {newqueue_threads}")
                    log.debug(f"Number of Queue Threads: {len(newqueue_threads)}")
                if len(queue_threads) == 0:
                    break
                queue_threads = newqueue_threads
                for thread in queue_threads:
                    thread.join(timeout=0.1)
                time.sleep(0.5)
            log.debug(f"Intial Log Threads: {log_threads}")
            log.debug(f"Number of intial Log Threads: {len(log_threads)}")
            while True:
                new_logthreads = list(filter(lambda x: x and x.is_alive(), log_threads))
                if len(new_logthreads) != len(log_threads):
                    log.debug(f"Remaining Log Threads: {new_logthreads}")
                    log.debug(f"Number of Log Threads: {len(new_logthreads)}")
                if len(new_logthreads) == 0:
                    break
                log_threads = new_logthreads
                for thread in log_threads:
                    thread.join(timeout=0.1)
                time.sleep(0.5)
            log.debug(f"Initial download threads: {processes}")
            log.debug(f"Initial Number of download threads: {len(processes)}")
            while True:
                new_proceess = list(filter(lambda x: x and x.is_alive(), processes))
                if len(new_proceess) != len(processes):
                    log.debug(f"Remaining Processes: {new_proceess}")
                    log.debug(f"Number of Processes: {len(new_proceess)}")
                if len(new_proceess) == 0:
                    break
                processes = new_proceess
                for process in processes:
                    process.join(timeout=15)
                    if process.is_alive():
                        process.terminate()
                time.sleep(0.5)
            download_log_clear_helper()
            progress_updater.remove_download_task(task1)
            setDirectoriesDate(log)
            final_log(username)
            return final_log_text(username)
    except KeyboardInterrupt as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                [process.terminate() for process in processes]
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except:
            with exit.DelayedKeyboardInterrupt():
                raise E
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                [process.terminate() for process in processes]
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except Exception:
            with exit.DelayedKeyboardInterrupt():
                raise E




def queue_process(pipe_, task1, total):
    count = 0
    # shared globals
    while True:
        if count == 1:
            break
        try:
            if not pipe_.poll(timeout=1) :
                continue
            results = pipe_.recv()
            if not isinstance(results, list):
                results = [results]
        except Exception as E:
            common_globals.log.traceback_(E)
            common_globals.log.traceback_(traceback.format_exc())
            continue
        for result in results:
            try:
                if isinstance(result, list) or isinstance(result, tuple):
                    media_type, num_bytes_downloaded, total_size = result
                    with common_globals.count_lock:
                        common_globals.total_bytes_downloaded = (
                            common_globals.total_bytes_downloaded + num_bytes_downloaded
                        )
                        common_globals.total_bytes = (
                            common_globals.total_bytes + total_size
                        )
                        if media_type == "images":
                            common_globals.photo_count += 1

                        elif media_type == "videos":
                            common_globals.video_count += 1
                        elif media_type == "audios":
                            common_globals.audio_count += 1
                        elif media_type == "skipped":
                            common_globals.skipped += 1
                        elif media_type == "forced_skipped":
                            common_globals.forced_skipped += 1
                        log_download_progress(media_type)
                        progress_updater.update_download_task(
                            task1,
                            description=common_globals.desc.format(
                                p_count=common_globals.photo_count,
                                v_count=common_globals.video_count,
                                a_count=common_globals.audio_count,
                                skipped=common_globals.skipped,
                                forced_skipped=common_globals.forced_skipped,
                                total_bytes_download=convert_num_bytes(
                                    common_globals.total_bytes_downloaded
                                ),
                                total_bytes=convert_num_bytes(
                                    common_globals.total_bytes
                                ),
                                mediacount=total,
                                sumcount=common_globals.video_count
                                + common_globals.audio_count
                                + common_globals.photo_count
                                + common_globals.skipped
                                + common_globals.forced_skipped,
                            ),
                            refresh=True,
                            completed=common_globals.video_count
                            + common_globals.audio_count
                            + common_globals.photo_count
                            + common_globals.skipped
                            + common_globals.forced_skipped,
                        )

                elif result is None or result == "None":
                    count = count + 1
                elif isinstance(result, dict) and "dir_update" in result:
                    addGlobalDir(result["dir_update"])
                elif callable(result):
                    job_progress_helper(result)
            except Exception as E:
                common_globals.log.traceback_t(E)
                common_globals.log.traceback_(traceback.format_exc())
                #increase skipped
                common_globals.skipped += 1


def get_mediasplits(medialist):
    user_count = settings.get_threads()
    final_count = max(min(user_count, system.getcpu_count(), len(medialist) // 20), 1)
    return more_itertools.divide(final_count, medialist)


def process_dict_starter(
    username,
    model_id,
    ele,
    stdout_logqueue,
    pipe_,
    dateDict,
    userNameList,
    argsCopy,
):
    #queue for file and discord
    file_logqueue=AioPipe()
    subProcessVariableInit(
        dateDict,
        userNameList,
        pipe_,
        argsCopy,
        stdout_logqueue,
        file_logqueue[0]
    )
    common_globals.log.debug(f"{pid_log_helper()} preparing thread")
    priority.setpriority()
    system.setNameAlt()
    plat = platform.system()
    if plat == "Linux":
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    other_logs.start_other_thread(
        input_=file_logqueue[1], name=str(os.getpid()), count=1
    )
    try:
        process_dicts_split(username, model_id, ele)
    except KeyboardInterrupt as E:
        with exit.DelayedKeyboardInterrupt():
            try:
                pipe_.send(None)
                common_globals.log.log(100,None)
                raise E
            except Exception as E:
                raise E


def job_progress_helper(funct):
    try:
        funct()
    #probably handle by other thread
    except KeyError:
        pass
    except Exception as E:
        logging.getLogger("shared").debug(E)


async def ajob_progress_helper(funct):
    try:
        await asyncio.get_event_loop().run_in_executor(
                None,
                funct,
        )
    #probably handle by other thread
    except KeyError:
        pass
    except Exception as E:
        logging.getLogger("shared").debug(E)

async def consumer(lock,aws):
    i=0
    while True:
        async with lock:
            if not(bool(aws)):
                break
            data = aws.pop()
        if data is None:
            break
        else:
            try:
                pack = await download(*data)
                common_globals.log.debug(f"unpack {pack} count {len(pack)}")
                media_type, num_bytes_downloaded = pack
                await send_msg((media_type, num_bytes_downloaded, 0))
            except Exception as e:
                common_globals.log.info(f"Download Failed because\n{e}")
                common_globals.log.traceback_(traceback.format_exc())
                media_type = "skipped"
                num_bytes_downloaded = 0
                await send_msg((media_type, num_bytes_downloaded, 0))


@run
async def process_dicts_split(username, model_id, medialist):
    medialist = list(medialist)
    common_globals.log.debug(f"{pid_log_helper()} starting process")
    common_globals.log.debug(
        f"{pid_log_helper()} process mediasplit from total {len(medialist)}"
    )
    aws = []
    async with download_session() as c:
        for ele in medialist:
            aws.append((c, ele, model_id, username))
        concurrency_limit = get_max_workers()
        lock = asyncio.Lock()
        consumers = [
            asyncio.create_task(consumer(lock,aws)) for _ in range(concurrency_limit)
        ]

        await asyncio.gather(*consumers)
    common_globals.log.debug(f"{pid_log_helper()} download process thread closing")
    # send message directly
    await asyncio.get_event_loop().run_in_executor(common_globals.thread, cache.close)
    common_globals.thread.shutdown()
    common_globals.log.log(100,None)
    await send_msg({"dir_update": common_globals.localDirSet})
    await send_msg(None)


def pid_log_helper():
    return f"PID: {os.getpid()}"


async def download(c, ele, model_id, username):
    # set logs for mpd
    set_media_log(common_globals.log, ele)
    common_globals.attempt.set(0)
    try:
        if read_args.retriveArgs().metadata:
            return await metadata(c, ele, username, model_id)
        #conditions for download
        if ele.url:
            data=await main_download(c, ele, username, model_id)
        elif ele.mpd:
            data=await alt_download(c, ele, username, model_id)
        common_globals.log.debug(f"{get_medialog(ele)} Download finished")
        return data
    except Exception as e:
        common_globals.log.traceback_(f"{get_medialog(ele)} Download Failed\n{e}")
        common_globals.log.traceback_(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        # we can put into seperate otherqueue_
        return "skipped", 0