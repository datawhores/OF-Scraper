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
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.common.check import update_check
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")
API = "Labels"


@run
async def get_labels(model_id, c=None):
    labels_ = await get_labels_data(model_id, c=c)
    labels_ = (
        labels_
        if not settings.get_settings().label
        else list(
            filter(
                lambda x: x.get("name").lower() in settings.get_settings().label,
                labels_,
            )
        )
    )
    data = await get_posts_for_labels(labels_, model_id, c=c)
    update_check(data, model_id, None, API)

    return data


async def get_labels_data(model_id, c=None):
    generators = [scrape_labels(c, model_id)]
    return await process_tasks_labels(generators)


async def get_posts_for_labels(labels, model_id, c=None):
    generators = []
    for label in labels:
        generators.append(scrape_posts_labels(c, label, model_id))

    labels_final = await process_tasks_get_posts_for_labels(generators, labels)
    return labels_final


async def process_tasks_labels(generators):
    output = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Label Names Pages Progress: {page_count}", visible=True
    )
    seen = set()
    queue = asyncio.Queue()

    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue

        page_count += 1
        progress_utils.api.update_overall_task(
            page_task,
            description=f"Label Names Pages Progress: {page_count}",
        )

        if batch:
            new_labels = [
                label
                for label in batch
                if label.get("id") not in seen and not seen.add(label.get("id"))
            ]
            log.debug(
                f"{common_logs.PROGRESS_IDS.format('Label Names')} {list(map(lambda x: x['id'], new_labels))}"
            )
            trace_progress_log(f"{API} names tasks", new_labels)
            output.extend(new_labels)

    progress_utils.api.remove_overall_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Labels Names')} {list(map(lambda x: x['id'], output))}"
    )
    trace_log_raw(f"{API} names final", output, final_count=True)
    log.debug(
        f"{common_logs.FINAL_COUNT_ITEM.format('Label Names', len(output), 'labels')}"
    )
    return output


async def process_tasks_get_posts_for_labels(generators, labels):
    responseDict = get_default_label_dict(labels)
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Labels Progress: {page_count}", visible=True
    )
    queue = asyncio.Queue()

    async def producer(gen):
        try:
            async for label_info, batch in gen:
                await queue.put((label_info, batch))
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        result = await queue.get()
        if result is None:
            active_workers -= 1
            continue

        label_info, batch = result
        page_count += 1
        progress_utils.api.update_overall_task(
            page_task, description=f"Labels Progress: {page_count}"
        )

        if batch:
            new_posts = label_dedupe(responseDict[label_info["id"]]["seen"], batch)
            log.debug(
                f"{common_logs.PROGRESS_IDS.format('Label Content')} {list(map(lambda x: x['id'], new_posts))}"
            )
            trace_progress_log(f"{API} content tasks", new_posts)
            responseDict[label_info["id"]]["posts"].extend(new_posts)

    # Clean up 'seen' sets
    [label.pop("seen", None) for label in responseDict.values()]

    # Detailed debugging for final IDs (Matches original structure)
    log.debug(
        f"{common_logs.FINAL_IDS.format('All Labels Content')} {[item['id'] for value in responseDict.values() for item in value.get('posts', [])]}"
    )
    log.debug(
        f"{common_logs.FINAL_IDS.format('Labels Individual Content')}\n"
        + "\n".join(
            [
                f"{responseDict[key]['id']}:{list(map(lambda x: x['id'], responseDict[key]['posts']))}"
                for key in responseDict.keys()
            ]
        )
    )

    # Detailed summary counts
    log.debug(
        common_logs.FINAL_COUNT_POST.format(
            "All Labels Content",
            len(
                [
                    item["id"]
                    for value in responseDict.values()
                    for item in value.get("posts", [])
                ]
            ),
        )
    )
    log.debug(
        f"{common_logs.FINAL_COUNT.format('Labels Individual Content ->')}\n"
        + "\n".join(
            [
                f"{responseDict[key]['id']}:{len(responseDict[key]['posts'])} posts"
                for key in responseDict.keys()
            ]
        )
    )

    trace_log_raw(f"{API} content final", list(responseDict.values()), final_count=True)
    progress_utils.api.remove_overall_task(page_task)

    return list(responseDict.values())


async def scrape_labels(c, model_id, offset=0):
    current_offset = offset
    while True:
        url = of_env.getattr("labelsEP").format(model_id, current_offset)
        task = None
        log.debug(
            f"trying to access label names with url:{url}  offset:{current_offset}"
        )
        try:
            task = progress_utils.api.add_job_task(
                f"labels offset -> {current_offset}", visible=True
            )
            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Labels API Error: {r.status} for {url}")

                    break

                data = await r.json_()
                log.debug(
                    f"successfully access label names with url:{url}  offset:{current_offset}"
                )

                media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
                batch = media_lists[0] if media_lists else []

                log.debug(f"offset:{current_offset} -> labels names found {len(batch)}")
                log.debug(
                    f"offset:{current_offset} -> hasMore value in json {data.get('hasMore','undefined')}"
                )

                trace_progress_log(f"{API} names requests", data)

                if not batch:
                    break

                yield batch

                if not data.get("hasMore"):
                    break

                current_offset += len(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


async def scrape_posts_labels(c, label, model_id, offset=0):
    current_offset = offset
    while True:
        url = of_env.getattr("labelledPostsEP").format(
            model_id, current_offset, label["id"]
        )
        task = None
        log.debug(
            f"trying to access label content with url:{url}  offset:{current_offset}"
        )
        try:
            task = progress_utils.api.add_job_task(
                f": getting posts from label -> {label['name']}", visible=True
            )
            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Labels Post API Error: {r.status} for {url}")
                    break

                data = await r.json_()
                log.debug(
                    f"successfully access label content with url:{url}  offset:{current_offset}"
                )

                media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
                batch = media_lists[0] if media_lists else []

                log.debug(
                    f"offset:{current_offset} -> labelled posts found {len(batch)}"
                )
                log.debug(
                    f"offset:{current_offset} -> hasMore value in json {data.get('hasMore','undefined')}"
                )

                trace_progress_log(f"{API} content requests", data)

                if not batch:
                    break

                yield label, batch

                if not data.get("hasMore"):
                    break

                current_offset += len(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


def label_dedupe(seen, labelArray):
    return [
        post
        for post in labelArray
        if post.get("id") not in seen and not seen.add(post.get("id"))
    ]


def get_default_label_dict(labels):
    output = {}
    for label in labels:
        label_copy = label.copy()
        output[label_copy["id"]] = label_copy
        output[label_copy["id"]]["seen"] = set()
        output[label_copy["id"]]["posts"] = []
    return output
