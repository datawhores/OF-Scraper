r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import asyncio
from functools import partial

import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater

from ofscraper.classes.sessionmanager.download import download_session
from ofscraper.actions.utils.log import final_log, final_log_text
from ofscraper.actions.utils.paths.paths import setDirectoriesDate
from ofscraper.actions.utils.buffer import download_log_clear_helper

from ofscraper.actions.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
from ofscraper.actions.actions.metadata.normal.utils.consumer import consumer
from ofscraper.actions.actions.metadata.utils.desc import desc


@run
async def process_dicts(username, model_id, medialist):
    download_log_clear_helper()
    task1 = None
    with progress_utils.setup_metadata_progress_live():
        common_globals.mainProcessVariableInit()
        try:

            aws = []

            async with download_session() as c:
                for ele in medialist:
                    aws.append((c, ele, model_id, username))
                task1 = progress_updater.add_metadata_task(
                    desc.format(
                        p_count=0,
                        v_count=0,
                        a_count=0,
                        skipped=0,
                        mediacount=len(medialist),
                        forced_skipped=0,
                        sumcount=0,
                        total_bytes_download=0,
                        total_bytes=0,
                    ),
                    total=len(aws),
                    visible=True,
                )
                concurrency_limit = get_max_workers()
                lock = asyncio.Lock()
                consumers = [
                    asyncio.create_task(consumer(aws, task1, medialist, lock))
                    for _ in range(concurrency_limit)
                ]
                await asyncio.gather(*consumers)
        except Exception as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        finally:
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread, cache.close
            )
            common_globals.thread.shutdown()

        setDirectoriesDate()
        download_log_clear_helper()
        progress_updater.remove_metadata_task(task1)
        final_log(username)
        return final_log_text(username)
