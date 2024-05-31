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
import psutil
from aioprocessing import AioPipe

import ofscraper.download.shared.general as common
import ofscraper.download.shared.globals.globals as common_globals
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit
import ofscraper.utils.dates as dates
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.other as other_logs
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.manager as manager_
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.download.alt_downloadbatch import alt_download
from ofscraper.download.main_downloadbatch import main_download
from ofscraper.download.shared.classes.session import download_session
from ofscraper.download.shared.general import (
    get_medialog,
    subProcessVariableInit,
)
from ofscraper.download.shared.log import final_log, final_log_text   ,log_download_progress,set_media_log
from ofscraper.download.shared.metadata import metadata
from ofscraper.download.shared.paths.paths import addGlobalDir, setDirectoriesDate
from ofscraper.download.shared.progress.progress import convert_num_bytes
from ofscraper.utils.context.run_async import run
from ofscraper.download.shared.workers import get_max_workers

platform_name = platform.system()


def process_dicts(username, model_id, filtered_medialist):
    metadata_md = read_args.retriveArgs().metadata
    log = logging.getLogger("shared")
    common_globals.log = log
    live = (
        partial(progress_utils.setup_download_progress_live, multi=True)
        if not metadata_md
        else partial(progress_utils.setup_metadata_progress_live)
    )
    try:
        common_globals.reset_globals()
        with live():
            if not read_args.retriveArgs().item_sort:
                random.shuffle(filtered_medialist)
            manager = manager_.get_manager()
            mediasplits = get_mediasplits(filtered_medialist)
            num_proc = len(mediasplits)
            split_val = min(4, num_proc)
            log.debug(f"Number of download threads: {num_proc}")
            connect_tuples = [AioPipe() for _ in range(num_proc)]
            shared = list(
                more_itertools.chunked([i for i in range(num_proc)], split_val)
            )
            # shared with other process + main
            logqueues_ = [manager.Queue() for _ in range(len(shared))]
            # other logger queuesprocesses
            otherqueues_ = [manager.Queue() for _ in range(len(shared))]
            # shared cache

            # start stdout/main queues consumers
            log_threads = [
                stdout_logs.start_stdout_logthread(
                    input_=logqueues_[i],
                    name=f"ofscraper_{model_id}_{i+1}",
                    count=len(shared[i]),
                )
                for i in range(len(shared))
            ]
            processes = [
                aioprocessing.AioProcess(
                    target=process_dict_starter,
                    args=(
                        username,
                        model_id,
                        mediasplits[i],
                        logqueues_[i // split_val],
                        otherqueues_[i // split_val],
                        connect_tuples[i][1],
                        dates.getLogDate(),
                        selector.get_ALL_SUBS_DICT(),
                        read_args.retriveArgs(),
                    ),
                )
                for i in range(num_proc)
            ]
            [process.start() for process in processes]
            task1 = progress_utils.add_download_task(
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
            progress_utils.remove_download_task(task1)
            setDirectoriesDate()
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
    final_log(username)
    return final_log_text(username)


def queue_process(pipe_, task1, total):
    count = 0
    # shared globals

    while True:
        if count == 1:
            break
        results = pipe_.recv()
        if not isinstance(results, list):
            results = [results]

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
                        progress_utils.update_download_task(
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

                elif result is None:
                    count = count + 1
                elif isinstance(result, dict) and "dir_update" in result:
                    addGlobalDir(result["dir_update"])
                elif callable(result):
                    job_progress_helper(result)
            except Exception as E:
                console.get_console().print(E)
                console.get_console().print(traceback.format_exc())


def get_mediasplits(medialist):
    user_count = settings.get_threads()
    final_count = max(min(user_count, system.getcpu_count(), len(medialist) // 5), 1)
    return more_itertools.divide(final_count, medialist)


def process_dict_starter(
    username,
    model_id,
    ele,
    p_logqueue_,
    p_otherqueue_,
    pipe_,
    dateDict,
    userNameList,
    argsCopy,
):
    subProcessVariableInit(
        dateDict,
        userNameList,
        pipe_,
        logger.get_shared_logger(
            main_=p_logqueue_, other_=p_otherqueue_, name=f"shared_{os.getpid()}"
        ),
        argsCopy,
    )
    setpriority()
    plat = platform.system()
    if plat == "Linux":
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
   
    try:
        process_dicts_split(username, model_id, ele)
    except KeyboardInterrupt as E:
        with exit.DelayedKeyboardInterrupt():
            try:
                p_otherqueue_.put("None")
                p_logqueue_.put("None")
                pipe_.send(None)
                raise E
            except Exception as E:
                raise E


def job_progress_helper(funct):
    try:
        with common_globals.chunk_lock:
            funct()
    except Exception as E:
        logging.getLogger("shared").debug(E)


def setpriority():
    os_used = platform.system()
    process = psutil.Process(
        os.getpid()
    )  # Set highest priority for the python script for the CPU
    if os_used == "Windows":  # Windows (either 32-bit or 64-bit)
        process.ionice(psutil.IOPRIO_NORMAL)
        process.nice(psutil.NORMAL_PRIORITY_CLASS)

    elif os_used == "Linux":  # linux
        process.ionice(psutil.IOPRIO_CLASS_BE)
        process.nice(5)
    else:  # MAC OS X or other
        process.nice(10)


async def consumer(queue):
    while True:
        data = await queue.get()
        if data==None:
            break
        try:
            pack= await download(*data)
            common_globals.log.debug(f"unpack {pack} count {len(pack)}")
            media_type, num_bytes_downloaded = pack
            await common.send_msg((media_type, num_bytes_downloaded, 0))
        except Exception as e:
                common_globals.log.info(f"Download Failed because\n{e}")
                common_globals.log.traceback_(traceback.format_exc())
                media_type = "skipped"
                num_bytes_downloaded = 0
                await common.send_msg((media_type, num_bytes_downloaded, 0))
        queue.task_done()
        await asyncio.sleep(1)


async def producer(queue, aws,concurrency_limit):
    for data in aws:
        await queue.put(data)
    await queue.put(None)
    for _ in range(concurrency_limit):
        await queue.put(None)
    queue.join()  # Wait for all tasks to finish


@run
async def process_dicts_split(username, model_id, medialist):
    common_globals.log.debug(f"{pid_log_helper()} start inner thread for other loggers")
    # set variables based on parent process
    # start consumer for other
    other_logs.start_other_thread(
        input_=common_globals.log.handlers[1].queue, name=str(os.getpid()), count=1
    )
    
    medialist = list(medialist)
    # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8

    common_globals.log.debug(f"{pid_log_helper()} starting process")
    common_globals.log.debug(
        f"{pid_log_helper()} process mediasplit from total {len(medialist)}"
    )
    aws = []
    async with download_session() as c:
        for ele in medialist:
            aws.append((c, ele, model_id, username))
        concurrency_limit= get_max_workers()
        queue = asyncio.Queue(maxsize=concurrency_limit)
        consumers = [asyncio.create_task(consumer(queue)) for _ in range(concurrency_limit)]
        await producer(queue, aws,concurrency_limit)
        await asyncio.gather(*consumers)
    common_globals.log.debug(f"{pid_log_helper()} download process thread closing")
    # send message directly
    await asyncio.get_event_loop().run_in_executor(
        common_globals.thread, cache.close
    )
    common_globals.thread.shutdown()
    common_globals.log.handlers[0].queue.put("None")
    common_globals.log.handlers[1].queue.put("None")
    common_globals.log.debug("other thread closed")
    await common.send_msg({"dir_update": common_globals.localDirSet})
    await common.send_msg(None)


def pid_log_helper():
    return f"PID: {os.getpid()}"






async def download(c, ele, model_id, username):
    #set logs for mpd
    set_media_log(common_globals.log,ele)
    templog_ = logger.get_shared_logger(
        name=str(ele.id), main_=aioprocessing.Queue(), other_=aioprocessing.Queue()
    )
    common_globals.innerlog.set(templog_)
    try:
        if read_args.retriveArgs().metadata:
            return await metadata(c, ele, username, model_id)
        elif ele.url:
            return await main_download(c, ele, username, model_id)
        elif ele.mpd:
            return await alt_download(c, ele, username, model_id)
    except Exception as e:
        common_globals.log.traceback_(
            f"{get_medialog(ele)} Download Failed\n{e}"
        )
        common_globals.log.traceback_(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        # we can put into seperate otherqueue_
        return "skipped", 0
    finally:
        common_globals.log.handlers[1].queue.put(
            list(common_globals.innerlog.get().handlers[1].queue.queue)
        )
        common_globals.log.handlers[0].queue.put(
            list(common_globals.innerlog.get().handlers[0].queue.queue)
        )
