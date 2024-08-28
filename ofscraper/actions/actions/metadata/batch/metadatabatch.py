import asyncio
import logging
import logging.handlers
import os
import platform
import random
import threading

import aioprocessing
from aioprocessing import AioPipe

import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.context.exit as exit
import ofscraper.utils.dates as dates
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater

import ofscraper.utils.system.system as system
import ofscraper.utils.system.priority as priority

from ofscraper.classes.sessionmanager.download import download_session
from ofscraper.actions.utils.globals import subProcessVariableInit
from ofscraper.actions.utils.log import (
    final_log,
    final_log_text,
)

from ofscraper.actions.utils.paths.paths import setDirectoriesDate
from ofscraper.actions.utils.send.message import send_msg
from ofscraper.actions.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.logs.other as other_logs

from ofscraper.utils.system.speed import add_pids_to_download_obj
from ofscraper.actions.utils.buffer import download_log_clear_helper
from ofscraper.actions.utils.mediasplit import get_mediasplits
from ofscraper.actions.actions.metadata.batch.utils.consumer import consumer
from ofscraper.actions.utils.threads import handle_threads, start_threads
from ofscraper.actions.actions.metadata.batch.utils.queue import queue_process
from ofscraper.actions.actions.metadata.utils.desc import desc
import  ofscraper.runner.manager as manager


platform_name = platform.system()


def process_dicts(username, model_id, filtered_medialist):
    log = logging.getLogger("shared")

    try:
        common_globals.main_globals()
        download_log_clear_helper()
        with progress_utils.setup_metadata_progress_live():
            if not read_args.retriveArgs().media_sort:
                random.shuffle(filtered_medialist)

            mediasplits = get_mediasplits(filtered_medialist)
            num_proc = len(mediasplits)
            log.debug(f"Number of download threads: {num_proc}")
            connect_tuples = [AioPipe() for _ in range(num_proc)]
            stdout_logqueues = [AioPipe() for _ in range(num_proc)]

            # start stdout/main queues consumers
            log_threads = []
            for i in range(num_proc):
                thread = stdout_logs.start_stdout_logthread(
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
                        manager.Manager.model_manager.all_subs_dict,
                        read_args.retriveArgs(),
                    ),
                )
                for i in range(num_proc)
            ]
            add_pids_to_download_obj(map(lambda x: x.pid, processes))

            task1 = progress_updater.add_metadata_task(
                desc.format(
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
            start_threads(queue_threads, processes)
            handle_threads(queue_threads, processes, log_threads)
            # for reading completed downloads
        download_log_clear_helper()
        progress_updater.remove_metadata_task(task1)
        setDirectoriesDate(log)
        final_log(username)
        return final_log_text(username)
    except KeyboardInterrupt as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                [process.terminate() for process in processes or []]
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
                [process.terminate() for process in processes or []]
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except Exception:
            with exit.DelayedKeyboardInterrupt():
                raise E


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
    # queue for file and discord
    file_logqueue = AioPipe()
    subProcessVariableInit(
        dateDict, userNameList, pipe_, argsCopy, stdout_logqueue, file_logqueue[0]
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
                common_globals.log.log(100, None)
                raise E
            except Exception as E:
                raise E


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
            asyncio.create_task(consumer(lock, aws)) for _ in range(concurrency_limit)
        ]

        await asyncio.gather(*consumers)
    common_globals.log.debug(f"{pid_log_helper()} download process thread closing")
    # send message directly
    await asyncio.get_event_loop().run_in_executor(common_globals.thread, cache.close)
    common_globals.thread.shutdown()
    common_globals.log.log(100, None)
    await send_msg({"dir_update": common_globals.localDirSet})
    await send_msg(None)


def pid_log_helper():
    return f"PID: {os.getpid()}"
