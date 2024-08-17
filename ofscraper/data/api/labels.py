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
import logging
import traceback

import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.common.check import update_check
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log

log = logging.getLogger("shared")
API = "labels"


@run
async def get_labels(model_id, c=None):
    labels_ = await get_labels_data(model_id, c=c)
    labels_ = (
        labels_
        if not read_args.retriveArgs().label
        else list(
            filter(
                lambda x: x.get("name").lower() in read_args.retriveArgs().label,
                labels_,
            )
        )
    )
    data = await get_posts_for_labels(labels_, model_id, c=c)
    update_check(data, model_id, None, API)

    return data


@run
async def get_labels_data(model_id, c=None):
    tasks = []
    tasks.append(asyncio.create_task(scrape_labels(c, model_id)))
    return await process_tasks_labels(tasks)


@run
async def get_posts_for_labels(labels, model_id, c=None):
    tasks = []

    [
        tasks.append(asyncio.create_task(scrape_posts_labels(c, label, model_id)))
        for label in labels
    ]
    labels_final = await process_tasks_get_posts_for_labels(tasks, labels)
    return labels_final


async def process_tasks_labels(tasks):
    responseArray = []

    page_count = 0

    page_task = progress_utils.add_api_task(
        f"Label Names Pages Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                progress_utils.update_api_task(
                    page_task,
                    description=f"Label Names Pages Progress: {page_count}",
                )

                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Label Names')} {list(map(lambda x:x['id'],new_posts))}"
                )
                trace_progress_log(f"{API} names tasks", new_posts)
                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    progress_utils.remove_api_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Labels Names')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_raw(f"{API} names final", responseArray, final_count=True)
    log.debug(f"{common_logs.FINAL_COUNT.format('Labels Name')} {len(responseArray)}")

    return responseArray


async def scrape_labels(c, model_id, offset=0):
    labels = None
    new_tasks = []

    url = constants.getattr("labelsEP").format(model_id, offset)
    task = None
    log.debug(f"trying access label names with url:{url}  offset:{offset}")

    try:

        task = progress_utils.add_api_job_task(
            f"labels offset -> {offset}",
            visible=True,
        )

        async with c.requests_async(url) as r:

            data = await r.json_()
            log.debug(
                f"successfully access label names with url:{url}  offset:{offset}"
            )

            labels = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            log.debug(f"offset:{offset} -> labels names found {len(labels)}")
            log.debug(
                f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            trace_progress_log(f"{API} names requests", data)

            if (
                data.get("hasMore")
                and len(data.get("list")) > 0
                and data.get("nextOffset") != offset
            ):
                offset = offset + len(data.get("list"))
                new_tasks.append(
                    asyncio.create_task(
                        scrape_labels(
                            c,
                            model_id,
                            offset=offset,
                        )
                    )
                )
            return data.get("list"), new_tasks
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        progress_utils.remove_api_job_task(task)


async def process_tasks_get_posts_for_labels(tasks, labels):
    responseDict = get_default_label_dict(labels)

    page_count = 0

    page_task = progress_utils.add_api_task(
        f"Labels Progress: {page_count}", visible=True
    )

    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                label, posts, new_tasks = await task
                page_count = page_count + 1
                progress_utils.update_api_task(
                    page_task, description=f"Labels Progress: {page_count}"
                )
                new_posts = label_dedupe(responseDict[label["id"]]["seen"], posts)
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Label Content')} {list(map(lambda x:x['id'],new_posts))}"
                )
                trace_progress_log(f"{API} content tasks", new_posts)
                responseDict[label["id"]]["posts"].extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
            tasks.extend(new_tasks)
        tasks = new_tasks
    [label.pop("seen", None) for label in responseDict.values()]
    log.debug(
        f"{common_logs.FINAL_IDS.format('All Labels Content')} {[item['id'] for value in responseDict.values() for item in value.get('posts', [])]}"
    )
    log.debug(
        f"{common_logs.FINAL_IDS.format('Labels Individual Content')}"
        + "\n".join(
            [
                f"{responseDict[key]['id']}:{list(map(lambda x:x['id'],responseDict[key]['posts']))}"
                for key in responseDict.keys()
            ]
        )
    )
    log.debug(
        f"{common_logs.FINAL_COUNT.format('All Labels Content')} {len([item['id'] for value in responseDict.values() for item in value.get('posts', [])])}"
    )
    log.debug(
        f"{common_logs.FINAL_COUNT.format('Labels Individual Content')}"
        + "\n".join(
            [
                f"{responseDict[key]['id']}:{len(responseDict[key]['posts'])}"
                for key in responseDict.keys()
            ]
        )
    )
    trace_log_raw(f"{API} content final", list(responseDict.values()), final_count=True)
    progress_utils.remove_api_task(page_task)
    return list(responseDict.values())


async def scrape_posts_labels(c, label, model_id, offset=0):
    posts = None
    new_tasks = []
    url = constants.getattr("labelledPostsEP").format(model_id, offset, label["id"])

    try:

        task = progress_utils.add_api_job_task(
            f": getting posts from label -> {label['name']}",
            visible=True,
        )
        log.debug(f"trying to access label names with url:{url}  offset:{offset}")

        async with c.requests_async(url) as r:

            data = await r.json_()
            log.debug(f"trying to access label names with url:{url}  offset:{offset}")

            posts = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            log.debug(f"offset:{offset} -> labelled posts found {len(posts)}")
            log.debug(
                f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            trace_progress_log(f"{API} content requests", data)

            if data.get("hasMore") and len(posts) > 0:
                offset += len(posts)
                new_tasks.append(
                    asyncio.create_task(
                        scrape_posts_labels(
                            c,
                            label,
                            model_id,
                            offset=offset,
                        )
                    )
                )

    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        progress_utils.remove_api_job_task(task)

    return label, posts, new_tasks


def label_dedupe(seen, labelArray):
    new_posts = [
        post
        for post in labelArray
        if post["id"] not in seen and not seen.add(post["id"])
    ]
    return new_posts


def get_default_label_dict(labels):
    output = {}
    for label in labels:
        output[label["id"]] = label
        output[label["id"]]["seen"] = set()
        output[label["id"]]["posts"] = []
    return output
