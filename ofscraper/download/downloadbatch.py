import asyncio
import logging
import logging.handlers
import os
import platform
import random
import threading
import time
import traceback

import aioprocessing
import more_itertools
import psutil
from aioprocessing import AioPipe
from humanfriendly import format_size
from rich.live import Live

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.download.common as common
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.other as other_logs
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.manager as manager_
import ofscraper.utils.system.system as system
from ofscraper.download.alt_downloadbatch import alt_download
from ofscraper.download.common import (
    addGlobalDir,
    convert_num_bytes,
    get_medialog,
    log_download_progress,
    reset_globals,
    setDirectoriesDate,
    setupProgressBar,
    subProcessVariableInit,
)
from ofscraper.download.main_downloadbatch import main_download
from ofscraper.utils.context.run_async import run

platform_name = platform.system()


def process_dicts(username, model_id, filtered_medialist):
    log = logging.getLogger("shared")
    common.log = log
    try:
        reset_globals()
        if not read_args.retriveArgs().item_sort:
            random.shuffle(filtered_medialist)
        manager = manager_.get_manager()
        mediasplits = get_mediasplits(filtered_medialist)
        num_proc = len(mediasplits)
        split_val = min(4, num_proc)
        log.debug(f"Number of process {num_proc}")
        connect_tuples = [AioPipe() for _ in range(num_proc)]
        shared = list(more_itertools.chunked([i for i in range(num_proc)], split_val))
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
                    dates.getLogDateVManager(),
                    selector.get_ALL_SUBS_DICTVManger(),
                    read_args.retriveArgsVManager(),
                ),
            )
            for i in range(num_proc)
        ]
        [process.start() for process in processes]
        progress_group, overall_progress, job_progress = setupProgressBar(multi=True)

        task1 = overall_progress.add_task(
            common.desc.format(
                p_count=common.photo_count,
                v_count=common.video_count,
                a_count=common.audio_count,
                skipped=common.skipped,
                mediacount=len(filtered_medialist),
                sumcount=common.video_count
                + common.audio_count
                + common.photo_count
                + common.skipped,
                forced_skipped=common.forced_skipped,
                data=common.data,
                total=common.total_data,
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
                    overall_progress,
                    job_progress,
                    task1,
                    len(filtered_medialist),
                ),
                daemon=True,
            )
            for i in range(num_proc)
        ]
        [thread.start() for thread in queue_threads]
        with stdout.lowstdout():
            with Live(
                progress_group,
                refresh_per_second=constants.getattr("refreshScreen"),
                console=console.get_shared_console(),
            ):
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
                    new_logthreads = list(
                        filter(lambda x: x and x.is_alive(), log_threads)
                    )
                    if len(new_logthreads) != len(log_threads):
                        log.debug(f"Remaining Log Threads: {new_logthreads}")
                        log.debug(f"Number of Log Threads: {len(new_logthreads)}")
                    if len(new_logthreads) == 0:
                        break
                    log_threads = new_logthreads
                    for thread in log_threads:
                        thread.join(timeout=0.1)
                    time.sleep(0.5)
                log.debug(f"Initial Processes: {processes}")
                log.debug(f"Initial Number of Processes: {len(processes)}")
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
        overall_progress.remove_task(task1)
        progress_group.renderables[1].height = 0
        setDirectoriesDate()
    except KeyboardInterrupt as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                [process.terminate() for process in processes]
                manager.shutdown()
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
                manager.shutdown()
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except Exception:
            with exit.DelayedKeyboardInterrupt():
                raise E
    log.warning(
        f"[bold]{username}[/bold] ({format_size(common.total_bytes )}) ({common.photo_count+common.audio_count+common.video_count} \
downloads total [{common.video_count} videos, {common.audio_count} audios, {common.photo_count} photos], \
{common.forced_skipped} skipped, {common.skipped} failed)"
    )
    return (
        common.photo_count,
        common.video_count,
        common.audio_count,
        common.forced_skipped,
        common.skipped,
    )


def queue_process(pipe_, overall_progress, job_progress, task1, total):
    count = 0
    downloadprogress = (
        read_args.retriveArgs().downloadbars or config_data.get_show_downloadprogress()
    )
    # shared globals

    while True:
        if (
            count == 1
            or overall_progress.tasks[task1].total
            == overall_progress.tasks[task1].completed
        ):
            break
        results = pipe_.recv()
        if not isinstance(results, list):
            results = [results]

        for result in results:
            if result is None:
                count = count + 1
                continue
            if isinstance(result, dict) and not downloadprogress:
                continue
            if isinstance(result, set):
                addGlobalDir(result)
                continue
            if isinstance(result, dict):
                job_progress_helper(job_progress, result)
                continue
            media_type, num_bytes_downloaded, total_size = result
            with common.count_lock:
                common.total_bytes_downloaded = (
                    common.total_bytes_downloaded + num_bytes_downloaded
                )
                common.total_bytes = common.total_bytes + total_size

                data = convert_num_bytes(common.total_bytes_downloaded)
                total_data = convert_num_bytes(common.total_bytes)
                if media_type == "images":
                    common.photo_count += 1

                elif media_type == "videos":
                    common.video_count += 1
                elif media_type == "audios":
                    common.audio_count += 1
                elif media_type == "skipped":
                    common.skipped += 1
                elif media_type == "forced_skipped":
                    common.forced_skipped += 1
                log_download_progress(media_type)
                overall_progress.update(
                    task1,
                    description=common.desc.format(
                        p_count=common.photo_count,
                        v_count=common.video_count,
                        a_count=common.audio_count,
                        skipped=common.skipped,
                        forced_skipped=common.forced_skipped,
                        data=data,
                        total=total_data,
                        mediacount=total,
                        sumcount=common.video_count
                        + common.audio_count
                        + common.photo_count
                        + common.skipped
                        + common.forced_skipped,
                    ),
                    refresh=True,
                    completed=common.video_count
                    + common.audio_count
                    + common.photo_count
                    + common.skipped
                    + common.forced_skipped,
                )


def get_mediasplits(medialist):
    user_count = read_args.retriveArgs().downloadthreads or config_data.get_threads()
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


def job_progress_helper(job_progress, result):
    funct = {
        "add_task": job_progress.add_task,
        "update": job_progress.update,
        "remove_task": job_progress.remove_task,
    }.get(result.pop("type"))
    if funct:
        try:
            with common.chunk_lock:
                funct(*result.pop("args"), **result)
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


@run
async def process_dicts_split(username, model_id, medialist):
    common.log.debug(f"{pid_log_helper()} start inner thread for other loggers")
    # set variables based on parent process
    # start consumer for other
    other_thread = other_logs.start_other_thread(
        input_=common.log.handlers[1].queue, name=str(os.getpid()), count=1
    )
    medialist = list(medialist)
    # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8

    common.log.debug(f"{pid_log_helper()} starting process")
    common.log.debug(
        f"{pid_log_helper()} process mediasplit from total {len(medialist)}"
    )

    aws = []

    async with sessionbuilder.sessionBuilder() as c:
        for ele in medialist:
            aws.append(asyncio.create_task(download(c, ele, model_id, username)))

        for coro in asyncio.as_completed(aws):
            try:
                pack = await coro
                common.log.debug(f"unpack {pack} count {len(pack)}")
                media_type, num_bytes_downloaded = pack
                await common.send_msg((media_type, num_bytes_downloaded, 0))
            except Exception as e:
                common.log.traceback_(f"Download Failed because\n{e}")
                common.log.traceback_(traceback.format_exc())
                media_type = "skipped"
                num_bytes_downloaded = 0
                await common.send_msg((media_type, num_bytes_downloaded, 0))

    common.log.debug(f"{pid_log_helper()} download process thread closing")
    # send message directly
    await asyncio.get_event_loop().run_in_executor(
        common.cache_thread, common.cache.close
    )
    common.cache_thread.shutdown()
    common.log.handlers[0].queue.put("None")
    common.log.handlers[1].queue.put("None")
    if other_thread:
        other_thread.join()
    common.log.debug("other thread closed")
    await common.send_msg(common.localDirSet)
    await common.send_msg(None)


def pid_log_helper():
    return f"PID: {os.getpid()}"


async def download(c, ele, model_id, username):
    # reduce number of logs
    async with common.maxfile_sem:
        templog_ = logger.get_shared_logger(
            name=str(ele.id), main_=aioprocessing.Queue(), other_=aioprocessing.Queue()
        )
        common.innerlog.set(templog_)
        try:
            if ele.url:
                return await main_download(c, ele, username, model_id)
            if ele.mpd:
                return await alt_download(c, ele, username, model_id)
        except Exception as e:
            common.innerlog.get().traceback_(
                f"{get_medialog(ele)} Download Failed\n{e}"
            )
            common.innerlog.get().traceback_(
                f"{get_medialog(ele)} exception {traceback.format_exc()}"
            )
            # we can put into seperate otherqueue_
            return "skipped", 0
        finally:
            common.log.handlers[1].queue.put(
                list(common.innerlog.get().handlers[1].queue.queue)
            )
            common.log.handlers[0].queue.put(
                list(common.innerlog.get().handlers[0].queue.queue)
            )
