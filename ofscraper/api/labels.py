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

import ofscraper.api.common.logs as common_logs
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
from ofscraper.utils.context.run_async import run
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")


@run
async def get_labels_progress(model_id, c=None):
    labels_ = await get_labels_data_progress(model_id, c=c)
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
    return await get_posts_for_labels_progress(labels_, model_id, c=c)


@run
async def get_labels_data_progress(model_id, c=None):
    tasks = []
    tasks.append(
        asyncio.create_task(
            scrape_labels(c, model_id, job_progress=progress_utils.labelled_progress)
        )
    )
    progress_utils.labelled_layout.visible = False
    return await process_tasks_labels(tasks)


@run
async def get_posts_for_labels_progress(labels, model_id, c=None):
    tasks = []

    [
        tasks.append(
            asyncio.create_task(
                scrape_posts_labels(
                    c, label, model_id, job_progress=progress_utils.labelled_progress
                )
            )
        )
        for label in labels
    ]
    labels_final = await process_tasks_get_posts_for_labels(tasks, labels, model_id)
    progress_utils.labelled_layout.visible = False
    return labels_final


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
    return await get_posts_for_labels(labels_, model_id, c=c)


@run
async def get_labels_data(model_id, c=None):
    with progress_utils.set_up_api_labels():
        tasks = []
        tasks.append(
            asyncio.create_task(
                scrape_labels(
                    c, model_id, job_progress=progress_utils.labelled_progress
                )
            )
        )
        return await process_tasks_labels(tasks)


@run
async def get_posts_for_labels(labels, model_id, c=None):
    with progress_utils.set_up_api_posts_labels():
        tasks = []
        [
            tasks.append(
                asyncio.create_task(
                    scrape_posts_labels(
                        c,
                        label,
                        model_id,
                        job_progress=progress_utils.labelled_progress,
                    )
                )
            )
            for label in labels
        ]
        return await process_tasks_get_posts_for_labels(tasks, labels, model_id)


async def process_tasks_labels(tasks):
    responseArray = []

    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
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
                overall_progress.update(
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
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Label Names')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                new_posts,
                            )
                        )
                    )
                )
                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    overall_progress.remove_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Labels Names')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_task(responseArray)
    log.debug(f"{common_logs.FINAL_COUNT.format('Labels Name')} {len(responseArray)}")

    return responseArray


async def scrape_labels(c, model_id, job_progress=None, offset=0):
    labels = None
    new_tasks = []
    await asyncio.sleep(1)
    url = constants.getattr("labelsEP").format(model_id, offset)
    task = None

    try:

        task = (
            job_progress.add_task(
                f"labels offset -> {offset}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url) as r:
            data = await r.json_()
            labels = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            log.debug(f"offset:{offset} -> labels names found {len(labels)}")
            log.debug(
                f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            log.trace(
                "offset:{offset} -> label names raw: {posts}".format(
                    offset=offset, posts=data
                )
            )

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
                            job_progress=job_progress,
                            offset=offset,
                        )
                    )
                )
            return data.get("list"), new_tasks
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        await asyncio.sleep(1)

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        (job_progress.remove_task(task) if job_progress and task is not None else None)


async def process_tasks_get_posts_for_labels(tasks, labels, model_id):
    responseDict = get_default_label_dict(labels)

    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
        f"Labels Progress: {page_count}", visible=True
    )

    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                label, new_posts, new_tasks = await task
                page_count = page_count + 1
                overall_progress.update(
                    page_task, description=f"Labels Progress: {page_count}"
                )
                unduped_posts = label_dedupe(
                    responseDict[label["id"]]["seen"], new_posts
                )
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Label Content')} {list(map(lambda x:x['id'],unduped_posts))}"
                )
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Label Content')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                unduped_posts,
                            )
                        )
                    )
                )

                responseDict[label["id"]]["posts"].extend(unduped_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
            tasks.extend(new_tasks)
        tasks = new_tasks
    [label.pop("seen", None) for label in responseDict.values()]
    set_check(responseDict.values(), model_id)
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
    trace_log_task(list(responseDict.values()), header="All Labels Content")
    overall_progress.remove_task(page_task)
    return list(responseDict.values())


async def scrape_posts_labels(c, label, model_id, job_progress=None, offset=0):
    posts = None
    new_tasks = []
    url = constants.getattr("labelledPostsEP").format(model_id, offset, label["id"])
    tasks = None

    await asyncio.sleep(1)
    try:

        task = (
            job_progress.add_task(
                f": getting posts from label -> {label['name']}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url) as r:
            data = await r.json_()
            posts = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            log.debug(f"offset:{offset} -> labelled posts found {len(posts)}")
            log.debug(
                f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            log.trace(
                "{offset} -> {posts}".format(
                    offset=offset,
                    posts="\n\n".join(
                        map(
                            lambda x: f"scrapeinfo label {str(x)}",
                            posts,
                        )
                    ),
                )
            )

            if data.get("hasMore") and len(posts) > 0:
                offset += len(posts)
                new_tasks.append(
                    asyncio.create_task(
                        scrape_posts_labels(
                            c,
                            label,
                            model_id,
                            job_progress=job_progress,
                            offset=offset,
                        )
                    )
                )

    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        (job_progress.remove_task(task) if job_progress and task is not None else None)

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


def set_check(unduped, model_id):
    cache.set(
        f"labels_check_{model_id}",
        list(unduped),
        expire=constants.getattr("THREE_DAY_SECONDS"),
    )
    cache.close()


def trace_log_task(responseArray, header=None):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    for i in range(1, len(responseArray) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(
            i + chunk_size - 1, len(responseArray)
        )  # Adjust end_index calculation
        chunk = responseArray[i - 1 : end_index]  # Adjust slice to start at i-1
        api_str = "\n\n".join(
            map(lambda post: f"{common_logs.RAW_INNER} {post}\n\n", chunk)
        )
        log.trace(
            f"{common_logs.FINAL_RAW.format(header or 'Labels Names')}".format(
                posts=api_str
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements
