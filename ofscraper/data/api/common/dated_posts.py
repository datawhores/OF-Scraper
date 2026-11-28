"""The timeline, archived and streams scans, which differ only in names and endpoints.

All three page oldest-first by ``postedAtPrecise`` from a start point worked out
from the database, split the cached posts into chunks with one worker each,
and flag cached posts the API no longer returns as deleted.

``timeline.py``, ``archive.py`` and ``streams.py`` keep their public functions
as thin wrappers. Each passes its own module as ``m`` (for shared-name hooks
such as ``m.get_tasks`` and ``m.mark_post_as_deleted``) and passes its own
area-specific callables (``post_info``, ``media``, ``youngest_date``,
``scrape``) at call time, so patching a name on the area module changes only
that area's scan. Shared utilities (``settings``, ``of_env``, ``incomplete``,
``log``) are read directly here.
"""

import logging
import math
import traceback
from dataclasses import dataclass

import arrow

import ofscraper.data.api.common.incomplete as incomplete
import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.const as const
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
from ofscraper.data.api.tasks import collect_pages

log = logging.getLogger("shared")


@dataclass(frozen=True)
class Area:
    # "Archived": logs, progress, cache and check-mode keys
    api: str
    # of_env keys: first page, later pages, and the most post ids that are
    # fetched one by one instead of scanning
    endpoint: str
    next_endpoint: str
    max_individual: str
    # trace title of the cached posts
    cache_trace: str
    # end of the "Flagging N ..." line
    ghosts: str
    # log each batch's post ids at debug level as pages arrive
    log_progress_ids: bool = False
    # log the final ids and count once the pages are merged
    log_final: bool = False


async def get_posts(m, model_id, username, c=None, post_id=None):
    area = m.AREA
    after = incomplete.start_scan(
        model_id, area.api, await m.get_after(model_id, username)
    )
    m.time_log(username, after)
    post_id = post_id or []
    if len(post_id) == 0 or len(post_id) > of_env.getattr(area.max_individual):
        splitArrays = await m.get_split_array(model_id, username, after)
        generators = m.get_tasks(splitArrays, c, model_id, username, after)
        data = await m.process_tasks_batch(generators)
        incomplete.save_scan(model_id, area.api, after, username)
    else:
        data = m.process_posts_as_individual()
    m.update_check(data, model_id, after, area.api)
    return data


async def get_old_posts(m, post_info, model_id, username):
    if not settings.get_settings().api_cached_disabled:
        oldposts = await post_info(model_id=model_id, username=username)
    else:
        oldposts = []
    oldposts = list(filter(lambda x: x is not None, oldposts))
    seen = set()
    oldposts = [
        post
        for post in oldposts
        if post["post_id"] not in seen and not seen.add(post["post_id"])
    ]
    log.debug(f"[bold]{m.AREA.api} Cache[/bold] {len(oldposts)} found")
    trace_log_raw(m.AREA.cache_trace, oldposts)
    return oldposts


async def process_tasks_batch(m, generators):
    api = m.AREA.api

    def on_new(new_posts):
        if m.AREA.log_progress_ids:
            log.debug(
                f"{common_logs.PROGRESS_IDS.format(api)} {list(map(lambda x: x['id'], new_posts))}"
            )
        trace_progress_log(f"{api} task", new_posts)

    responseArray = await collect_pages(
        generators,
        f"{api} Content Pages Progress",
        on_new,
    )
    if m.AREA.log_final:
        log.debug(
            f"{common_logs.FINAL_IDS.format(api)} {list(map(lambda x: x.get('id'), responseArray))}"
        )
        trace_log_raw(f"{api} final", responseArray, final_count=True)
        log.debug(common_logs.FINAL_COUNT_POST.format(api, len(responseArray)))
    return responseArray


def _parse_created_at(value):
    if value in (None, ""):
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    return ts if math.isfinite(ts) else None


def split_posts(m, oldposts, after):
    dated_posts = []
    for x in oldposts:
        ts = _parse_created_at(x.get("created_at"))
        if ts is None:
            continue
        row = x if isinstance(x.get("created_at"), (int, float)) else {**x, "created_at": ts}
        dated_posts.append((ts, row))
    if len(dated_posts) == 0:
        return []
    min_posts = m.get_min_posts_batch(len(dated_posts), m.AREA.api)
    dated_posts.sort(key=lambda pair: pair[0])
    filteredArray = [x for ts, x in dated_posts if ts >= after]

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]
    return splitArrays


def get_tasks(scrape, splitArrays, c, model_id, username, after):
    tasks = []

    # Scenario 1: Empty DB, or just hunting for brand new posts today
    if len(splitArrays) == 0:
        tasks.append(
            scrape(
                c, model_id, username, timestamp=after, is_last_chunk=True, offset=True
            )
        )
        return tasks

    # If our 'after' anchor is older than our first known database record,
    # spawn a worker to sweep the gap between 'after' and the first known post.
    first_known_post = splitArrays[0][0]
    first_known_timestamp = float(first_known_post.get("created_at"))

    if float(after) < first_known_timestamp:
        log.debug(
            f"Spawning Bridge Worker to cover gap from {after} to {first_known_timestamp}"
        )
        tasks.append(
            scrape(
                c,
                model_id,
                username,
                timestamp=after,
                required_posts=[
                    {
                        "post_id": first_known_post.get("post_id"),
                        "timestamp": first_known_timestamp,
                    }
                ],
                offset=True,
            )
        )

    # Scenarios 2 & 3: Iterate through the known chunks dynamically
    for i, chunk in enumerate(splitArrays):
        is_first_chunk = i == 0
        is_final_chunk = i == len(splitArrays) - 1

        # Overlap logic: Start at the first element, or the last element of the previous chunk
        start_timestamp = (
            chunk[0].get("created_at")
            if is_first_chunk
            else splitArrays[i - 1][-1].get("created_at")
        )

        tasks.append(
            scrape(
                c,
                model_id,
                username,
                timestamp=start_timestamp,
                required_posts=[
                    {"post_id": ele.get("post_id"), "timestamp": ele.get("created_at")}
                    for ele in chunk
                ],
                is_last_chunk=is_final_chunk,
                offset=is_first_chunk or is_final_chunk,
            )
        )

    return tasks


async def scrape_posts(
    m,
    c,
    model_id,
    username,
    timestamp=None,
    required_posts=None,
    is_last_chunk=False,
    offset=False,
):
    area = m.AREA
    required_posts = required_posts or []
    expected_missing = [p for p in required_posts]
    required_ids = {p["post_id"] for p in required_posts}

    before = arrow.get(settings.get_settings().before or arrow.now()).float_timestamp
    start_anchor = float(timestamp) if timestamp else 0
    all_ghosts_found = []

    current_timestamp = float(timestamp) - 0.001 if timestamp and offset else timestamp
    # after the first page the cursor is a post's date, which is used even if 0
    paged = False
    has_more = True

    try:
        while has_more:
            url = (
                of_env.getattr(area.next_endpoint).format(
                    model_id, str(current_timestamp)
                )
                if current_timestamp or paged
                else of_env.getattr(area.endpoint).format(model_id)
            )

            log.debug(f"Fetching {area.api} API: {url}")
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"{area.api} API Error: {r.status} for {url}")
                    incomplete.mark_incomplete(model_id, area.api, f"HTTP {r.status}")
                    break

                data = await r.json_()
                batch = data.get("list", [])
                has_more = data.get("hasMore", False)
                if not batch:
                    break
                log.debug(f"Received batch with {len(batch)} items.")

                # an undated post is kept; it doesn't move the page cursor
                batch_timestamps = []
                for x in batch:
                    if x.get("postedAtPrecise") in (None, ""):
                        log.warning(f"{area.api}: post {x.get('id')} has no date")
                        batch_timestamps.append(None)
                    else:
                        batch_timestamps.append(float(x["postedAtPrecise"]))
                dated = [ts for ts in batch_timestamps if ts is not None]
                if not dated:
                    log.warning(
                        f"{area.api}: no post on this page has a date, stopping the scan here"
                    )
                    if has_more:
                        incomplete.mark_incomplete(
                            model_id, area.api, "no post on page has a date"
                        )
                    yield batch
                    break
                max_ts = max(dated)
                batch_ids = {x["id"] for x in batch}

                expected_missing = [
                    p for p in expected_missing if p["post_id"] not in batch_ids
                ]
                for ele in batch:
                    required_ids.discard(ele["id"])

                ghosts_in_batch = []
                for expected in expected_missing:
                    if max_ts >= expected["timestamp"] >= start_anchor:
                        ghosts_in_batch.append(expected["post_id"])

                if ghosts_in_batch:
                    all_ghosts_found.extend(ghosts_in_batch)
                    expected_missing = [
                        p
                        for p in expected_missing
                        if p["post_id"] not in ghosts_in_batch
                    ]
                    for g_id in ghosts_in_batch:
                        required_ids.discard(g_id)

                # Boundary condition: this page reaches past the "before" date limit.
                # Keep its in-range posts before stopping.
                if max_ts > before:
                    log.debug("Passed the user's '--before' upper boundary. Exiting.")
                    yield [
                        x
                        for x, ts in zip(batch, batch_timestamps, strict=True)
                        if ts is None or ts <= before
                    ]
                    break

                # This chunk has found all of its cached posts. Keep the page
                # that contained them; the next chunk only starts after its tail.
                if not is_last_chunk and len(required_ids) == 0:
                    log.debug(
                        "All required gap IDs found or resolved as ghosts. Exiting early."
                    )
                    yield batch
                    break

                if has_more and paged and max_ts <= current_timestamp:
                    log.warning(
                        f"{area.api}: page cursor did not advance, stopping the scan here"
                    )
                    incomplete.mark_incomplete(
                        model_id, area.api, "page cursor did not advance"
                    )
                    yield batch
                    break

                current_timestamp = max_ts
                paged = True
                yield batch

    except Exception as E:
        incomplete.mark_incomplete(model_id, area.api, f"{type(E).__name__}: {E}")
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
    finally:
        if all_ghosts_found:
            log.info(
                f"Worker finished. Flagging {len(all_ghosts_found)} {area.ghosts}"
            )
            log.debug(
                f"Flagging the following post_ids as deleted for {username}: {all_ghosts_found}"
            )
            await m.mark_post_as_deleted(
                post_ids=all_ghosts_found, model_id=model_id, username=username
            )


async def get_after(m, media, youngest_date, model_id, username):
    api = m.AREA.api
    prechecks = m.get_after_pre_checks(model_id, api)
    if prechecks is not None:
        return max(
            arrow.get(prechecks).float_timestamp, arrow.get("2000").float_timestamp
        )

    curr = await media(model_id=model_id, username=username)
    if len(curr) == 0:
        return arrow.get("2000").float_timestamp

    curr_downloaded = await m.get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    deleted_posts = await m.get_deleted_post_ids(model_id=model_id, username=username)

    active_media = settings.get_settings().mediatypes or ["Videos", "Audios", "Images"]
    active_media_mapped = {
        const.MEDIA_ALIASES.get(t.lower(), t.lower()) for t in active_media
    }

    # 1. Filter out what we already have, what is dead, OR what we don't want
    filtered_items = [
        x
        for x in curr
        if x.get("downloaded") != 1
        and x.get("media_id") not in curr_downloaded
        and x.get("post_id") not in deleted_posts
        and x.get("unlocked") != 0
        and const.MEDIA_ALIASES.get(
            str(x.get("media_type", "")).lower(), str(x.get("media_type", "")).lower()
        )
        in active_media_mapped
    ]

    if len(filtered_items) == 0:
        youngest = await youngest_date(model_id=model_id, username=username)
        return date_or_2000(youngest)

    # 3. Deduplicate (Keeping newest instance for anchor)
    unique_missing = {}
    for item in filtered_items:
        mid = item.get("media_id")
        if mid not in unique_missing or arrow.get(
            item.get("posted_at") or 0
        ) > arrow.get(unique_missing[mid].get("posted_at") or 0):
            unique_missing[mid] = item

    # 4. Sort and return the oldest gap anchor
    missing_items = sorted(
        list(unique_missing.values()), key=lambda x: arrow.get(x.get("posted_at") or 0)
    )
    return date_or_2000(missing_items[0]["posted_at"])


def date_or_2000(value):
    # media dates can be Arrow objects, and an undated one (1970) is
    # still truthy; it falls back to 2000 as a missing float date does
    return arrow.get(value or 0).float_timestamp or arrow.get("2000").float_timestamp
