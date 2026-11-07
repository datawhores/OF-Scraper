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
from types import SimpleNamespace

import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.common.check import update_check
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.after import get_after_pre_checks
from ofscraper.db.operations_.labels import get_all_labels_posts
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_model_media_status,
)
from ofscraper.db.operations_.posts import get_deleted_post_ids
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.const as const

log = logging.getLogger("shared")
API = "Labels"


@run
async def get_labels(model_id, c=None, username=None):
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
    known = await get_known_label_posts(labels_, model_id, username)
    # Check mode (no username) always scans fully and leaves the marks alone.
    data = await get_posts_for_labels(
        labels_, model_id, c=c, known=known, track=bool(username)
    )
    update_check(data, model_id, None, API)

    return data


# Labels whose scan reached the end in this run, per model. Their "finished"
# mark is written only once the run has saved what the next run relies on
# (label rows and media rows), by commit_finished_labels.
_finished_labels = {}


def mark_label_finished(model_id, label_id):
    _finished_labels.setdefault(model_id, set()).add(label_id)


def commit_finished_labels(model_id):
    for label_id in _finished_labels.pop(model_id, set()):
        cache.set(label_complete_key(model_id, label_id), True)


def discard_finished_labels(model_id):
    _finished_labels.pop(model_id, None)


async def get_labels_data(model_id, c=None):
    generators = [scrape_labels(c, model_id)]
    return await process_tasks_labels(generators)


def label_complete_key(model_id, label_id):
    return f"labels_v2_complete_{model_id}_{label_id}"


async def get_posts_missing_media(model_id, username):
    """
    Post ids that still have media to download, filtered the same way as the
    timeline's get_after: not downloaded, not deleted, not locked, and of a
    media type this run downloads.
    """
    rows = await get_model_media_status(model_id=model_id, username=username)
    if not rows:
        return set()
    downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    deleted = await get_deleted_post_ids(model_id=model_id, username=username)
    active_media = settings.get_settings().mediatypes or ["Videos", "Audios", "Images"]
    active_mapped = {const.MEDIA_ALIASES.get(m.lower(), m.lower()) for m in active_media}
    return {
        str(x.get("post_id"))
        for x in rows
        if x.get("downloaded") != 1
        and x.get("media_id") not in downloaded
        and x.get("post_id") not in deleted
        and x.get("unlocked") != 0
        and const.MEDIA_ALIASES.get(
            str(x.get("media_type", "")).lower(), str(x.get("media_type", "")).lower()
        )
        in active_mapped
    }


async def get_known_label_posts(labels, model_id, username):
    """
    Post ids already recorded for each label, so a repeat scan can stop at the
    first page that holds nothing new. A label is left out (scanned fully) when:
    - no username is given (check mode),
    - a full scan is requested as for the timeline (--after, incremental
      downloads off, like/unlike),
    - its last scan didn't finish cleanly (an error or 429 cut it short), or
    - one of its recorded posts still has media to download, so that post is
      offered for download again as it is today.
    """
    if not username:
        return {}
    if get_after_pre_checks(model_id, API) is not None:
        log.debug(f"{API}: full scan requested, scanning every label from the start")
        return {}
    try:
        missing = await get_posts_missing_media(model_id, username)
    except Exception as E:
        log.debug(f"{API}: could not read download status, scanning fully: {E}")
        return {}
    known = {}
    for label in labels:
        if not cache.get(label_complete_key(model_id, label["id"]), default=False):
            log.debug(f"{API}: label {label['id']} last scan incomplete, full scan")
            continue
        try:
            ids = await get_all_labels_posts(
                SimpleNamespace(label_id=label["id"]),
                model_id=model_id,
                username=username,
            )
        except Exception as E:
            log.debug(f"{API}: no recorded posts for label {label.get('id')}: {E}")
            continue
        ids = {str(x) for x in ids or []}
        if ids & missing:
            log.debug(f"{API}: label {label['id']} has undownloaded media, full scan")
            continue
        known[label["id"]] = ids
    return known


async def get_posts_for_labels(labels, model_id, c=None, known=None, track=False):
    known = known or {}
    generators = []
    for label in labels:
        generators.append(
            scrape_posts_labels(
                c, label, model_id, known=known.get(label["id"]), track=track
            )
        )

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
    # Paging every label at once is what trips OnlyFans' rate limit (429s)
    sem = asyncio.Semaphore(max(1, int(of_env.getattr("LABELS_CONCURRENCY"))))

    async def producer(gen):
        try:
            async with sem:
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


async def scrape_posts_labels(c, label, model_id, offset=0, known=None, track=False):
    current_offset = offset
    known = known or set()
    # Marked incomplete until paging reaches its end and the run has saved
    # the results, so a scan cut short by an error, a 429 or a killed run
    # gets a full scan next time.
    if track:
        cache.set(label_complete_key(model_id, label["id"]), False)
    finished = False
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
                    finished = True
                    break

                yield label, batch

                if not data.get("hasMore"):
                    finished = True
                    break

                # Pages come newest first: once a whole page is already
                # recorded under this label, the older pages are too.
                if known and all(str(post.get("id")) in known for post in batch):
                    log.debug(
                        f"offset:{current_offset} -> every post already recorded for label {label['id']}, stopping"
                    )
                    finished = True
                    break

                current_offset += len(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)
    if finished and track:
        mark_label_finished(model_id, label["id"])


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
