import asyncio
import inspect
import logging
import queue
import re
import threading
import time
import traceback
from collections import defaultdict
from copy import deepcopy
from functools import partial

import arrow

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.table.app as app
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.data.api.archive as archived
import ofscraper.data.api.highlights as highlights
import ofscraper.data.api.labels as labels
import ofscraper.data.api.messages as messages_
import ofscraper.data.api.paid as paid_
import ofscraper.data.api.pinned as pinned
import ofscraper.data.api.profile as profile
import ofscraper.data.api.streams as streams
import ofscraper.data.api.timeline as timeline
import ofscraper.db.operations as operations
import ofscraper.managers.manager as manager
import ofscraper.sites as sites
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.console as console_
import ofscraper.utils.const as const
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
import ofscraper.utils.system.network as network
import ofscraper.utils.system.system as system
from ofscraper.classes.placeholder import media_type_keys
from ofscraper.classes.table.utils.post_metrics import build_post_centric_rows
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.commands.scraper.actions.download.download import process_dicts
from ofscraper.commands.utils.strings import check_str
from ofscraper.data.api.common.check import read_check, set_check
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.db.operations import make_changes_to_content_tables
from ofscraper.db.operations_.media import (
    batch_mediainsert,
    get_media_post_files_downloaded,
)
from ofscraper.filters.media.filters import undated_first
from ofscraper.main.close.final.final import final_action
from ofscraper.managers.postcollection import PostCollection
from ofscraper.scripts.after_download_action_script import after_download_action_script
from ofscraper.sites.fansly import scrape as fansly_scrape
from ofscraper.utils.checkers import AuthCheckLeft, AuthCheckUnavailable, check_auth
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
console = console_.get_shared_console()


ALL_MEDIA = {}
ROWS = {}
POST_ROWS = []
MEDIA_KEY = ["id", "postid", "username"]
check_user_dict = defaultdict(dict)
# the thread that downloads what the table sends; one for the whole session
_download_worker = None
# set while that thread works on a batch, from taking the rows to its cleanup
_downloading = threading.Event()


def process_download_queue():
    """
    Orchestrator function that processes the entire download queue in batches grouped by user.
    """
    while True:
        if app.row_queue.empty():
            time.sleep(1)
            continue
        _downloading.set()
        try:
            _process_queued_rows()
        finally:
            _downloading.clear()
            stop.clear()


def downloads_pending():
    """True while rows sent from the table wait or download."""
    if _download_worker is None or not _download_worker.is_alive():
        return False
    return not app.row_queue.empty() or _downloading.is_set()


def wait_for_downloads(poll=0.5):
    """Wait until what the table sent has finished downloading, so the menu
    doesn't come back with the downloads still running (#425)."""
    if not downloads_pending():
        return
    log.info("Finishing the downloads sent from the check table...")
    while downloads_pending():
        time.sleep(poll)
    log.info("The downloads sent from the check table have finished")


def _process_queued_rows():
    user_cart = defaultdict(lambda: {"posts": [], "media": [], "rows": []})
    while not app.row_queue.empty():
        try:
            key, row_data = app.row_queue.get_nowait()
            media_item, post_item, username, model_id = _get_data_from_row(row_data)

            # Append all necessary data for later processing
            user_cart[model_id]["posts"].append(post_item)
            user_cart[model_id]["media"].append(media_item)
            user_cart[model_id]["rows"].append((key, row_data))
            user_cart[model_id]["username"] = username  # Store username once

        except queue.Empty:
            break
        except Exception as e:
            log.debug(f"Error processing row from queue: {e}")
            log.traceback_(traceback.format_exc())

    # 2. PROCESS: Loop through each user's batch and process their items
    for model_id, data in user_cart.items():
        username = data["username"]
        if stop.requested.is_set():
            for key, _row in data["rows"]:
                app.app.update_cell_state(key, "[added]", "bold light_goldenrod2")
            continue
        log.info(f"Processing download batch for user: {username}")
        try:
            # Pass the user's entire batch to the processing function
            process_user_batch(
                username, model_id, data["media"], data["posts"], data["rows"]
            )

            # Run after-actions for this user
            if not stop.requested.is_set():
                after_download_action_script(username, data["media"], data["posts"])
            manager.Manager.current_model_manager.mark_as_processed(
                username, activity="download"
            )
            manager.Manager.stats_manager.update_and_print_stats(
                username, "download", data["media"]
            )

        except Exception as e:
            log.warning(
                f"An error occurred while processing the batch for {username}."
            )
            log.traceback_(e)

    # 3. FINAL CLEANUP: Now that all batches are processed, clear the queue
    try:
        final_action()
        manager.Manager.current_model_manager.clear_scrape_queues()
        manager.Manager.stats_manager.clear_scraper_activity_stats()
        log.info("Download processing complete. Waiting for new items...")
    except Exception as e:
        log.warning(
            f"An error occurred during the final cleanup phase. The cart state or stats may not have reset properly. {e}"
        )
        log.traceback_(traceback.format_exc())


def _get_data_from_row(row: dict):
    """
    Takes a row dictionary and returns fresh, deep copies of the
    corresponding data objects to prevent state issues between loops.
    """
    username = row["username"]
    media_id = int(row["media_id"])

    manager.Manager.current_model_manager.add_models(username, activity="download")
    model_obj = manager.Manager.current_model_manager.get_model(username)
    if not model_obj:
        raise Exception(f"Could not find model for username: {username}")

    m_id = str(model_obj.id)

    # Find the original, cached media object using the string key
    cached_media = check_user_dict[m_id]["collection"].find_media_item(media_id)
    if not cached_media:
        raise Exception(f"No media data found for media_id {media_id} from {username}")

    # Create fresh, deep copies to work with.
    fresh_media = deepcopy(cached_media)
    fresh_post = deepcopy(cached_media.post)

    return fresh_media, fresh_post, username, model_obj.id


def process_user_batch(
    username: str, model_id: int, media_list: list, post_list: list, row_list: list
):
    """
    Processes all media items for a single user's batch.

    Returns the batch's totals: "videos", "audios", "photos" and
    "forced" (skipped: files already there), "failed" (rows still failed
    after the retry) and "bytes" downloaded, for both passes. Each
    process_dicts call starts its counts again, so the caller can't read them
    afterwards.
    """
    totals = dict.fromkeys(
        ("videos", "audios", "photos", "forced", "failed", "bytes"), 0
    )
    if process_user_batch.counter == 0:
        log.info("Performing first-run CDM check...")
        if not network.check_cdm():
            # e.g. key mode cdrm, which is deprecated: the reason is shown above
            log.info("CDM check failed; DRM videos may not download. This check will not be repeated.")
        else:
            log.info("CDM check passed. This check will not be repeated.")
    process_user_batch.counter += 1

    operations.table_init_create(model_id=model_id, username=username)
    try:
        model_obj = manager.Manager.current_model_manager.get_model(username)
        status_text = "Active" if model_obj.active else "Expired"
        expire_date = model_obj.expired_string or "Unknown Date"
        log.warning(f"[{username}] Subscription: {status_text}")
        log.warning(f"[{username}] Expiration Date: {expire_date}")
    except Exception as e:
        log.debug(f"Could not print subscription status for {username}: {e}")

    m_id = str(model_id)

    target_media = list(media_list)
    target_posts = list(post_list)

    def refresh_media(indices):
        for i in indices:
            try:
                fresh_collection = check_user_dict[m_id]["collection"]
                target_media[i] = (
                    fresh_collection.find_media_item(target_media[i].id) or target_media[i]
                )
                target_posts[i] = target_media[i].post
            except Exception:
                pass

    def download_batch(indices, retry=False):
        failed = set(indices)
        reported = set()
        rows_by_media = defaultdict(list)
        for i in indices:
            rows_by_media[id(target_media[i])].append(i)
            log.info(f"Attempting to download: {target_media[i].filename} for {username}")

        def on_result(media, result):
            for i in rows_by_media[id(media)]:
                key, row = row_list[i]
                if result == "failed":
                    if retry:
                        log.info(f"Download failed for {media.filename}.")
                        app.app.update_cell_state(key, "[failed]", "bold red")
                        totals["failed"] += 1
                        reported.add(i)
                    continue
                failed.discard(i)
                media_list[i] = media
                post_list[i] = media.post
                if result == "stopped":
                    app.app.update_cell_state(key, "[stopped]", "bold cyan")
                elif result == "skipped":
                    log.info(f"Download skipped: {media.filename}")
                    app.app.update_cell_state(key, "[skipped]", "bold bright_yellow")
                else:
                    log.info(f"Download finished: {media.filename}")
                    _record_row_file(row, model_id, username, media)
                    app.app.update_cell_state(key, "[downloaded]", "bold green")
                reported.add(i)

        # a call that returns before downloading leaves the last batch's
        # bytes here
        common_globals.total_bytes_downloaded = 0
        try:
            if not stop.requested.is_set():
                counts = process_dicts(
                    username, model_id,
                    [target_media[i] for i in indices],
                    [target_posts[i] for i in indices],
                    on_result=on_result,
                )
                # not its failed count: a file failed in the first pass can
                # download in the retry, so "failed" counts the rows left
                for name, count in zip(
                    ("videos", "audios", "photos", "forced"), counts or (), strict=False
                ):
                    totals[name] += count
        except Exception as e:
            log.debug(f"Download batch failed: {e}")
        totals["bytes"] += common_globals.total_bytes_downloaded
        if stop.requested.is_set():
            for i in set(indices) - reported:
                media_list[i] = target_media[i]
                post_list[i] = target_posts[i]
                app.app.update_cell_state(row_list[i][0], "[added]", "bold light_goldenrod2")
            return []
        if retry:
            for i in sorted(set(indices) - reported):
                log.info(f"Download failed for {target_media[i].filename}.")
                app.app.update_cell_state(row_list[i][0], "[failed]", "bold red")
                totals["failed"] += 1
        return sorted(failed)

    indices = list(range(len(media_list)))
    refresh_media(indices)
    failed = download_batch(indices)
    if failed and not stop.requested.is_set():
        log.debug("Refreshing data and retrying...")
        try:
            if not _refresh_failed_posts(
                username, model_id, [target_media[i] for i in failed]
            ) and not stop.requested.is_set():
                data_refill(model_id)
        except stop.DownloadsStopped:
            pass  # Let download_batch restore the unreported rows below.
        if not stop.requested.is_set():
            time.sleep(1)
            refresh_media(failed)
        download_batch(failed, retry=True)
    return totals


# Initialize counter on the function object
process_user_batch.counter = 0
# the old name, which the GUI patch calls
_process_user_batch = process_user_batch


@run
async def _refresh_failed_posts(username, model_id, media):
    """Replace just the failed posts; False requests one creator-wide fallback."""
    seen = set()
    fresh_posts = []
    paid_posts = None
    try:
        for item in media:
            if stop.requested.is_set():
                return True
            post = item.post
            area = getattr(post, "responsetype", "").lower()
            post_id = getattr(post, "id", None)
            key = (area, post_id)
            if key in seen:
                continue
            seen.add(key)
            if area in {"paid", "purchased"}:
                # purchases can't be asked for one post: fetched once
                # (a Fansly purchase's area is "purchased")
                if paid_posts is None:
                    paid_posts = await _all_paid(username, model_id)
                data = next(
                    (p for p in paid_posts if str(p.get("id")) == str(post_id)),
                    None,
                )
            elif sites.is_fansly():
                data = await _fansly_refresh_post(area, post_id, model_id, username)
                if data is None:
                    return False
            elif area.capitalize() in const.TIMELINE_POST_AREA_SET:
                data = await asyncio.to_thread(get_individual_timeline_post, post_id)
            elif area == "messages":
                async with manager.Manager.session.aget_ofsession() as c:
                    data = await messages_.get_individual_messages_post(
                        model_id, post_id, c
                    )
            else:
                return False
            if stop.requested.is_set():
                return True
            data = data if isinstance(data, list) else [data]
            if not data or any(
                not isinstance(p, dict) or p.get("error") or not p.get("id")
                for p in data
            ):
                return False
            if not any(str(p["id"]) == str(post_id) for p in data):
                return False
            fresh_posts.extend(
                posts_.Post(
                    p, model_id, username, area,
                    purchased=bool(getattr(post, "purchase_type", None)),
                )
                for p in data
            )
        await process_post_media(username, model_id, fresh_posts)
        return True
    except Exception as e:
        log.debug(f"Couldn't refresh individual cart posts: {e}")
        return False


def _record_row_file(row, model_id, username, media):
    """Put the file the download recorded on its table row, so `o` opens
    its folder (#424)."""
    try:
        files = get_media_post_files_downloaded(
            model_id=model_id, username=username, media_id=media.id
        )
        # the file is recorded on every post of the media
        directory, filename = files.get(
            (media.id, media.post_id), next(iter(files.values()), (None, None))
        )
        row["directory"], row["filename"] = directory, filename
    except Exception as E:
        log.debug(f"Couldn't read the file path for media {media.id}: {E}")


@run
async def data_refill(model_id):
    if settings.get_settings().command == "msg_check":
        retriver = partial(message_check_retriver, forced=True)
    elif settings.get_settings().command == "paid_check":
        retriver = partial(purchase_check_retriver, forced=True)
    elif settings.get_settings().command == "story_check":
        retriver = partial(stories_check_retriver, forced=True)
    elif settings.get_settings().command == "post_check":
        retriver = partial(post_check_retriver, forced=True)
    else:
        return
    with progress_utils.TemporaryTaskState(progress_updater.activity):
        # refresh only the creator whose download failed
        async for username, refilled_id, final_post_array, *_ in retriver(
            only_model_id=model_id
        ):
            await process_post_media(username, refilled_id, final_post_array)


def _other_creator(model_id, only_model_id):
    # True when a refill for one creator should skip this one
    return only_model_id is not None and str(model_id) != str(only_model_id)


def allow_check_dupes():
    args = settings.get_args()
    args.force_all = True
    settings.update_args(args)


def get_areas():
    return settings.get_settings().check_area


def checker(menu=False):
    if _no_fansly_stories(settings.get_settings().command):
        if not menu:
            raise SystemExit(1)  # a usage error, like other refused commands
        return
    with stop.interrupt_handler():
        try:
            _checker()
        except stop.DownloadsStopped:
            if not menu:
                raise SystemExit(130) from None


def _no_fansly_stories(command):
    """Fansly has no stories check; True (after logging it) when asked."""
    if command == "story_check" and sites.is_fansly():
        log.error("The stories check is OnlyFans only; Fansly has no stories area")
        return True
    return False


def _checker():
    try:
        if settings.get_settings().command == "post_check":
            post_checker()
        elif settings.get_settings().command == "msg_check":
            message_checker()
        elif settings.get_settings().command == "paid_check":
            purchase_checker()
        elif settings.get_settings().command == "story_check":
            stories_checker()
    except (AuthCheckUnavailable, AuthCheckLeft):
        # the auth check runs in gather_rows now; its errors were never
        # logged as tracebacks
        raise
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


def set_after_check_mode():
    args = settings.get_args()
    args.after = 0
    settings.update_args(args)


def gather_rows(command):
    """The rows the check table shows for ``command`` (post_check, msg_check,
    paid_check or story_check), from the same scan of the creators and areas
    in the settings, without opening the table or starting its download
    thread. The check commands open the table on these; the GUI shows them
    itself. Rows add to the last scan's: call reset_table_data() first for
    a new table."""
    runners = {
        "post_check": post_check_runner,
        "msg_check": message_checker_runner,
        "paid_check": purchase_checker_runner,
        "story_check": stories_checker_runner,
    }
    if command not in runners:
        raise ValueError(f"Not a check command: {command}")
    if _no_fansly_stories(command):
        return []
    check_auth()
    allow_check_dupes()
    set_after_check_mode()
    runners[command]()
    return ROWS or []


def post_checker():
    gather_rows("post_check")
    start_helper()


async def _run_check(retriever):
    with (
        progress_utils.setup_live("api"),
        progress_utils.TemporaryTaskState(progress_updater.activity),
    ):
        async for user_name, model_id, final_post_array, *rest in retriever():
            skip_update = rest[0] if rest else None
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array,
                model_id=model_id,
                username=user_name,
                skip_update=skip_update,
            )
            await row_gather(user_name, model_id)


@run
@stop.fetching
async def post_check_runner():
    await _run_check(post_check_retriver)


@run
async def post_check_retriver(forced=False, only_model_id=None):
    user_dict = {}
    links = list(url_helper())
    if settings.get_settings().force:
        forced = True
    async with manager.Manager.session.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for ele in links:
            name_match = re.search(
                f"onlyfans.com/({of_env.getattr('USERNAME_REGEX')}+$)", ele
            )
            name_match2 = re.search(f"^{of_env.getattr('USERNAME_REGEX')}+$", ele)
            user_name = None
            model_id = None
            timeline_data = []
            labels_data = []
            pinned_data = []
            archived_data = []
            streams_data = []
            # areas read from the API in this run, not from the check cache
            fresh = set()

            if sites.is_fansly():
                user_name, model_id = await _fansly_creator(ele, c)
                if model_id is not None:
                    log.info(f"Getting Full Timeline for {user_name}")
                    user_dict.setdefault(model_id, {})["model_id"] = model_id
                    user_dict.setdefault(model_id, {})["username"] = user_name
            elif name_match:
                user_name = name_match.group(1)
                log.info(f"Getting Full Timeline for {user_name}")
                model_id = profile.get_id(user_name)
                user_dict.setdefault(model_id, {})["model_id"] = model_id
                user_dict.setdefault(model_id, {})["username"] = user_name

            elif name_match2:
                user_name = name_match2.group(0)
                model_id = profile.get_id(user_name)
                user_dict.setdefault(model_id, {})["model_id"] = model_id
                user_dict.setdefault(model_id, {})["username"] = user_name
            # no such account: get_id warned, go on with the next creator
            if model_id is None:
                continue
            if _other_creator(model_id, only_model_id):
                continue
            if user_dict.get(model_id) and model_id and user_name:
                progress_updater.activity.update_task(
                    description=check_str.format(
                        username=user_name, activity="Timeline posts"
                    ),
                    visible=True,
                )
                areas = _site_areas(get_areas(), user_name)
                await operations.table_init_create(
                    username=user_name, model_id=model_id
                )
                if "Timeline" in areas:
                    oldtimeline = read_check(model_id, timeline.API)
                    if oldtimeline is not None and not forced:
                        log.info(f"[{user_name}] Using cache for {timeline.API}")
                        timeline_data = oldtimeline
                    else:
                        log.info(
                            f"[{user_name}] Fetching fresh data for {timeline.API}"
                        )
                        timeline_data = await _get_timeline(model_id, user_name, c=c)
                        set_check(timeline_data, model_id, timeline.API)
                        fresh.add("Timeline")

                if "Archived" in areas:
                    oldarchive = read_check(model_id, archived.API)
                    if oldarchive is not None and not forced:
                        log.info(f"[{user_name}] Using cache for {archived.API}")
                        archived_data = oldarchive
                    else:
                        log.info(
                            f"[{user_name}] Fetching fresh data for {archived.API}"
                        )
                        archived_data = await archived.get_archived_posts(
                            model_id, user_name, c=c
                        )
                        set_check(archived_data, model_id, archived.API)
                        fresh.add("Archived")

                if "Pinned" in areas:
                    oldpinned = read_check(model_id, pinned.API)
                    if oldpinned is not None and not forced:
                        log.info(f"[{user_name}] Using cache for {pinned.API}")
                        pinned_data = oldpinned
                    else:
                        log.info(f"[{user_name}] Fetching fresh data for {pinned.API}")
                        pinned_data = await pinned.get_pinned_posts(model_id, c=c)
                        set_check(pinned_data, model_id, pinned.API)
                        fresh.add("Pinned")

                if "Labels" in areas:
                    oldlabels = read_check(model_id, labels.API)
                    if oldlabels is not None and not forced:
                        log.info(f"[{user_name}] Using cache for {labels.API}")
                        labels_data = oldlabels
                    else:
                        log.info(f"[{user_name}] Fetching fresh data for {labels.API}")
                        labels_resp = await labels.get_labels(model_id, c=c)
                        await operations.make_label_table_changes(
                            labels_resp,
                            model_id=model_id,
                            username=user_name,
                            posts=False,
                        )
                        labels_data = [
                            post
                            for label in labels_resp
                            for post in label.get("posts", [])
                        ]
                        set_check(labels_data, model_id, labels.API)
                        fresh.add("Labels")

                if "Streams" in areas:
                    oldstreams = read_check(model_id, streams.API)
                    if oldstreams is not None and not forced:
                        log.info(f"[{user_name}] Using cache for {streams.API}")
                        streams_data = oldstreams
                    else:
                        log.info(f"[{user_name}] Fetching fresh data for {streams.API}")
                        streams_data = await streams.get_streams_posts(
                            model_id, user_name, c=c
                        )
                        set_check(streams_data, model_id, streams.API)
                        fresh.add("Streams")

                in_order = [
                    ("Pinned", pinned_data),
                    ("Archived", archived_data),
                    ("Labels", labels_data),
                    ("Timeline", timeline_data),
                    ("Streams", streams_data),
                ]
                fresh_ids = {
                    post["id"] for name, data in in_order if name in fresh for post in data
                }
                await operations.make_post_table_changes(
                    # the last copy of a post is saved, so cached areas go
                    # first and a fresh copy always wins over a cached one
                    all_posts=[
                        post
                        for _, data in sorted(in_order, key=lambda area: area[0] in fresh)
                        for post in data
                    ],
                    model_id=model_id,
                    username=user_name,
                    # only posts the API returned now lose the deleted flag; a
                    # cached list can hold posts deleted since it was saved
                    from_api=fresh_ids,
                    # nor does --metadata write a cached copy over the row
                    skip_update={
                        post["id"] for _, data in in_order for post in data
                    }
                    - fresh_ids,
                )
                # only called in this iteration, so the loop variables are current
                def to_posts(data):
                    return list(
                        map(lambda x: posts_.Post(x, model_id, user_name), data)  # noqa: B023
                    )

                all_post_data = (
                    to_posts(pinned_data + archived_data + labels_data)
                    + timeline.filter_timeline_post(to_posts(timeline_data))
                    + to_posts(streams_data)
                )

                # saved above with fresh copies winning; this list can end on a
                # cached copy, so the runner's save doesn't update the rows
                yield user_name, model_id, all_post_data, True
        # individual links
        for ele in list(
            filter(
                lambda x: re.search(
                    f"onlyfans.com/{of_env.getattr('NUMBER_REGEX')}+/{of_env.getattr('USERNAME_REGEX')}+$",
                    x,
                ),
                links,
            )
        ):
            name_match = re.search(f"/({of_env.getattr('USERNAME_REGEX')}+$)", ele)
            num_match = re.search(f"/({of_env.getattr('NUMBER_REGEX')}+)", ele)
            if name_match and num_match:
                user_name = name_match.group(1)
                model_id = profile.get_id(user_name)
                if model_id is None or _other_creator(model_id, only_model_id):
                    continue
                progress_updater.activity.update_task(
                    description=check_str.format(
                        username=user_name, activity="Timeline posts"
                    ),
                    visible=True,
                )
                post_id = num_match.group(1)
                log.info(f"Getting individual link for {user_name}")
                resp = get_individual_timeline_post(post_id)
                data = posts_.Post(resp, model_id, user_name)
                yield user_name, model_id, [data], None


# Fansly's own pages: the first part of their links isn't a creator
FANSLY_PAGES = {
    "post", "live", "messages", "explore", "home", "notifications",
    "settings", "lists", "collection", "subscriptions", "vault", "search",
    "tags", "wallet",
}


async def _fansly_creator(name, c=None):
    """(username, account id) of the Fansly creator ``name`` (a username or
    an account id, or a link to their profile), or (None, None) when Fansly
    has no such account."""
    name = str(name or "").strip()
    link = re.search(r"fansly\.com/([^/?#]+)", name, re.IGNORECASE)
    if link:
        name = link.group(1)
        if name.lower() in FANSLY_PAGES:
            log.warning(
                f"Skipping a Fansly {name.lower()} link: check mode takes the "
                "creator's name or profile link"
            )
            return None, None
    if name:
        for found in await fansly_scrape.get_models([name], c=c):
            if name.lower() in (str(found["username"]).lower(), str(found["id"])):
                return found["username"], found["id"]
    log.warning(f"Skipping {name}: Fansly has no account by that name")
    return None, None


def _site_areas(areas, user_name):
    """The check areas the site has; Fansly has no pinned, archived or
    streams lists (pinned and archived posts are on its timeline)."""
    if not sites.is_fansly():
        return areas
    kept = [a for a in areas or [] if a in fansly_scrape.AREAS]
    skipped = [a for a in areas or [] if a not in fansly_scrape.AREAS]
    if skipped:
        log.info(f"[{user_name}] Fansly has no {', '.join(skipped)} area; skipped")
    return kept


async def _get_timeline(model_id, user_name, c=None):
    if sites.is_fansly():
        return await fansly_scrape.get_timeline_posts(model_id, user_name, c=c)
    return await timeline.get_timeline_posts(model_id, user_name, c=c)


async def _get_messages(model_id, user_name, c=None):
    if sites.is_fansly():
        return await fansly_scrape.get_messages(model_id, user_name, c=c)
    return await messages_.get_messages(model_id, user_name, c=c)


async def _get_paid(user_name, model_id, c=None):
    if sites.is_fansly():
        return await fansly_scrape.get_paid_posts(model_id, user_name, c=c)
    return await paid_.get_paid_posts(user_name, model_id, c=c)


async def _fansly_refresh_post(area, post_id, model_id, username):
    """A Fansly post again, by id, for a failed cart download; None when its
    area can't be asked for one post."""
    async with manager.Manager.session.aget_ofsession() as c:
        if area in {"timeline", "labels", "pinned", "archived", "post"}:
            return await fansly_scrape.get_timeline_posts(
                model_id, username, c=c, post_id=[post_id]
            )
        if area in {"messages", "message"}:
            return await fansly_scrape.get_messages(
                model_id, username, c=c, post_id=[post_id]
            )
    return None


async def _all_paid(username, model_id):
    """All the creator's purchased posts, for refreshing failed ones."""
    if sites.is_fansly():
        async with manager.Manager.session.aget_ofsession() as c:
            return await fansly_scrape.get_paid_posts(model_id, username, c=c)
    return await asyncio.to_thread(paid_.get_paid_posts, username, model_id)


def reset_data():
    # clean up args once check modes are ready to launch
    args = settings.get_args()
    if args.username:
        args.username = settings.get_settings().usernames = None
    settings.update_args(args)


def start_helper():
    global ROWS
    reset_data()
    network.check_cdm()
    thread_starters(ROWS)


def message_checker():
    gather_rows("msg_check")
    start_helper()


@run
@stop.fetching
async def message_checker_runner():
    await _run_check(message_check_retriver)


async def message_check_retriver(forced=False, only_model_id=None):
    links = list(url_helper())
    if settings.get_settings().force:
        forced = True
    async with manager.Manager.session.aget_ofsession() as c:
        for item in links:
            if not item:
                continue
            num_match = re.search(
                f"chats/(?:chat/)?({of_env.getattr('NUMBER_REGEX')}+)", item
            ) or re.search(f"^({of_env.getattr('NUMBER_REGEX')}+)$", item)
            name_match = re.search(f"^{of_env.getattr('USERNAME_REGEX')}+$", item)
            model_id = None
            user_name = None

            if sites.is_fansly():
                user_name, model_id = await _fansly_creator(item, c)
                if model_id is None:
                    continue
            elif num_match:
                model_id = num_match.group(1)
                user_name = profile.scrape_profile(model_id)["username"]
            elif name_match:
                user_name = name_match.group(0)
                model_id = profile.get_id(user_name)
            else:
                log.warning(
                    f"Skipping {item}: not a username, model id or chat link"
                )
                continue

            if _other_creator(model_id, only_model_id):
                continue
            if model_id and user_name:
                progress_updater.activity.update_task(
                    description=check_str.format(username=user_name, activity="Messages"),
                    visible=True,
                )
                log.info(f"Getting Messages/Paid content for {user_name}")
                await operations.table_init_create(
                    model_id=model_id, username=user_name
                )

                # --- Messages ---
                messages = None
                messages_fresh = False
                oldmessages = read_check(model_id, messages_.API)
                log.debug(f"Number of messages in cache {len(oldmessages or [])}")

                if oldmessages is not None and not forced:
                    log.info(f"[{user_name}] Using cache for {messages_.API}")
                    messages = oldmessages
                else:
                    log.info(f"[{user_name}] Fetching fresh data for {messages_.API}")
                    messages = await _get_messages(model_id, user_name, c=c)
                    set_check(messages, model_id, messages_.API)
                    messages_fresh = True

                message_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), messages)
                )
                await operations.make_messages_table_changes(
                    message_posts_array,
                    model_id=model_id,
                    username=user_name,
                    from_api=messages_fresh,
                    # nor does --metadata write a cached copy over the row
                    skip_update=not messages_fresh,
                )

                # --- Paid Content ---
                oldpaid = read_check(model_id, paid_.API)
                paid = None
                paid_fresh = False

                if oldpaid is not None and not forced:
                    log.info(f"[{user_name}] Using cache for {paid_.API}")
                    paid = oldpaid
                else:
                    log.info(f"[{user_name}] Fetching fresh data for {paid_.API}")
                    paid = await _get_paid(user_name, model_id, c=c)
                    set_check(paid, model_id, paid_.API)
                    paid_fresh = True

                paid_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name, purchased=True), paid)
                )

                final_post_array = paid_posts_array + message_posts_array
                # the messages are saved above, and a cached copy comes last in
                # this list; purchases are saved by the runner
                skip_update = {post.id for post in message_posts_array}
                if not paid_fresh:
                    skip_update |= {post.id for post in paid_posts_array}
                yield user_name, model_id, final_post_array, skip_update


def purchase_checker():
    gather_rows("paid_check")
    start_helper()


@run
@stop.fetching
async def purchase_checker_runner():
    await _run_check(purchase_check_retriver)


@run
async def purchase_check_retriver(forced=False, only_model_id=None):
    user_dict = {}
    if not sites.is_fansly():
        auth_requests.make_headers()
    if settings.get_settings().force:
        forced = True
    async with manager.Manager.session.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for name in check_usernames():
            if sites.is_fansly():
                user_name, model_id = await _fansly_creator(name, c)
            else:
                user_name = profile.scrape_profile(name)["username"]
                model_id = (
                    name if name.isnumeric() else profile.get_id(user_name, asked_for=name)
                )
            if model_id is None or _other_creator(model_id, only_model_id):
                continue
            progress_updater.activity.update_task(
                description=check_str.format(
                    username=user_name, activity="Purchased posts"
                ),
                visible=True,
            )
            user_dict[model_id] = user_dict.get(model_id, [])

            await operations.table_init_create(model_id=model_id, username=user_name)

            oldpaid = read_check(model_id, paid_.API)
            paid = None
            # a cached list can be days older than the rows: --metadata
            # leaves them alone
            skip_update = None

            if oldpaid is not None and not forced:
                log.info(f"[{user_name}] Using cache for {paid_.API}")
                paid = oldpaid
                skip_update = True
            elif user_name == of_env.getattr("DELETED_MODEL_PLACEHOLDER"):
                log.info(f"[{user_name}] Processing deleted model cache/data")
                paid_user_dict = await paid_.get_all_paid_posts()
                seen = set()
                paid = [
                    post
                    for post in paid_user_dict.get(str(model_id), [])
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
            else:
                log.info(f"[{user_name}] Fetching fresh data for {paid_.API}")
                paid = await _get_paid(user_name, model_id, c=c)
                set_check(paid, model_id, paid_.API)
            posts_array = list(
                map(lambda x: posts_.Post(x, model_id, user_name, purchased=True), paid)
            )
            yield user_name, model_id, posts_array, skip_update


def stories_checker():
    gather_rows("story_check")
    start_helper()


@run
@stop.fetching
async def stories_checker_runner():
    await _run_check(stories_check_retriver)


@run
async def stories_check_retriver(forced=False, only_model_id=None):
    user_dict = {}
    async with manager.Manager.session.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for name in check_usernames():
            user_name = profile.scrape_profile(name)["username"]
            model_id = profile.get_id(user_name, asked_for=name)
            if model_id is None or _other_creator(model_id, only_model_id):
                continue
            progress_updater.activity.update_task(
                description=check_str.format(
                    username=user_name, activity="Stories posts"
                )
            )
            user_dict[model_id] = user_dict.get(model_id, [])
            await operations.table_init_create(model_id=model_id, username=user_name)
            stories = await highlights.get_stories_post(model_id, c=c)
            highlights_ = await highlights.get_highlight_post(model_id, c=c)
            highlights_ = list(
                map(
                    lambda x: posts_.Post(x, model_id, user_name, "highlights"),
                    highlights_,
                )
            )
            stories = list(
                map(lambda x: posts_.Post(x, model_id, user_name, "stories"), stories)
            )
            yield user_name, model_id, stories + highlights_


def check_usernames():
    # usernames from -u and from the files given with -f
    current = settings.get_settings()
    return list(current.check_usernames or []) + list(
        getattr(current, "file_usernames", None) or []
    )


def url_helper():
    out = []
    out.extend(settings.get_settings().file or [])
    out.extend(settings.get_settings().url or [])
    return map(lambda x: x.strip(), out)


async def process_post_media(username, model_id, posts_array):
    m_id = str(model_id)
    check_user_dict[m_id].setdefault(
        "collection", PostCollection(username=username, model_id=m_id)
    )
    collection = check_user_dict[m_id]["collection"]
    collection.add_posts(posts_array, overwrite=True)
    media = collection.all_media
    await insert_media(username, model_id, media)
    return media


async def insert_media(username, model_id, media):
    await batch_mediainsert(
        media,
        model_id=model_id,
        username=username,
        downloaded=False,
    )


@run
async def get_paid_ids(model_id, user_name):
    oldpaid = read_check(model_id, paid_.API)
    paid = None

    if oldpaid is not None and not settings.get_settings().force:
        log.info(f"[{user_name}] Using cache for {paid_.API}")
        paid = oldpaid
    else:
        log.info(f"[{user_name}] Fetching fresh data for {paid_.API}")
        async with manager.Manager.session.aget_ofsession(
            sem_count=of_env.getattr("API_REQ_CHECK_MAX")
        ) as c:
            paid = await _get_paid(user_name, model_id, c=c)
            set_check(paid, model_id, paid_.API)

    media = await process_post_media(user_name, model_id, paid)
    media = list(filter(lambda x: x.canview is True, media))
    return list(map(lambda x: x.id, media))


def thread_starters(ROWS_):
    global _download_worker
    # one download thread: a second table opened from the menu reuses it
    if _download_worker is None or not _download_worker.is_alive():
        _download_worker = threading.Thread(target=process_download_queue, daemon=True)
        _download_worker.start()
    start_table(ROWS_)


def start_table(ROWS_, POST_ROWS_=None):
    loop = system.new_event_loop()
    asyncio.set_event_loop(loop)
    ROWS = ROWS_
    # a Textual app runs once, so each table gets a new one
    app.app = app.InputApp()
    app.app(table_data=ROWS, post_data=POST_ROWS_ if POST_ROWS_ is not None else POST_ROWS)


def reset_table_data():
    """Forget the last table's rows and media, so a table opened again from
    the menu shows only what it was opened for (#425)."""
    global ROWS, POST_ROWS
    ROWS = []
    POST_ROWS = []
    check_user_dict.clear()


def texthelper(text):
    text = text or ""
    text = inspect.cleandoc(text)
    text = re.sub(" +$", "", text)
    text = re.sub("^ +", "", text)
    text = re.sub("<[^>]*>", "", text)
    text = (
        text
        if len(text) < of_env.getattr("TABLE_STR_MAX")
        else f"{text[:of_env.getattr('TABLE_STR_MAX')]}..."
    )
    return text


def unlocked_helper(ele):
    # canview can be None when OnlyFans sends canView: null; the table
    # shows that as locked, like the cart cell does
    return bool(ele.canview)


def download_type_helper(ele):
    if ele.mpd:
        return "protected"
    elif ele.url:
        return "normal"
    return "unknown"


def datehelper(date):
    # the table treats this label as "no date" when sorting
    if date is None or date == "None":
        return "Probably Deleted"
    return date


def checkmarkhelper(ele):
    return "[]" if unlocked_helper(ele) else "Not Unlocked"


async def row_gather(username, model_id):
    global ROWS, POST_ROWS
    # with each file's directory and filename, for opening its folder (#424)
    downloaded = get_media_post_files_downloaded(model_id=model_id, username=username)

    m_id = str(model_id)
    collection = check_user_dict[m_id].get("collection")

    if not collection:
        raise Exception("No postcollection object found")

    media = collection.all_media
    out = []

    log.info(f"Generating UI Table with {len(media)} items... This may take a moment.")

    # newest first; undated media go last, as the oldest
    try:
        sorted_media = sorted(
            media, key=lambda x: undated_first(x.date), reverse=True
        )
    except Exception:
        # Fallback just in case the dates are poorly formatted
        try:
            sorted_media = sorted(
                media,
                key=lambda x: undated_first(arrow.get(x.date) if x.date else None),
                reverse=True,
            )
        except Exception as E:
            log.warning(f"Check table: couldn't sort media by date, left unsorted: {E!r}")
            sorted_media = list(media)

    # the posts each media id appears in, built once: calling
    # collection.posts_with_media_id per row rebuilds every media object each
    # time, so for a creator with ~14,000 items the table never finished
    posts_by_media = {}
    for item in media:
        posts_by_media.setdefault(item.id, set()).add(item.post_id)

    # "index" is the row's key in the table, so it must be unique across all
    # the creators in one table; "number" counts within this creator
    first_index = len(ROWS or []) + 1
    for count, ele in enumerate(sorted_media):
        # the date column shows the post's date
        if not ele.postdate:
            log.warning(
                f"Check table: media {ele.id} in post {ele.post_id} has no date"
            )
        is_unlocked = unlocked_helper(ele)
        is_downloaded = (ele.id, ele.post_id) in downloaded
        directory, filename = downloaded.get((ele.id, ele.post_id), (None, None))
        post_media_len = len(ele._post.post_media)
        dl_type = download_type_helper(ele)  # Calculate once for efficiency

        if is_downloaded:
            cart_state = "[downloaded]"
        elif not is_unlocked:
            cart_state = "Not Unlocked"
        elif dl_type == "unknown":
            cart_state = "Unknown"
        else:
            cart_state = "[]"

        other_posts = [p for p in posts_by_media.get(ele.id, ()) if p != ele.post_id]

        out.append(
            {
                "index": first_index + count,
                "number": count + 1,
                "download_cart": cart_state,
                "username": username,
                "downloaded": is_downloaded,
                "unlocked": is_unlocked,
                "download_type": dl_type,
                "other_posts_with_media": other_posts,
                "post_media_count": post_media_len,
                "mediatype": ele.mediatype.capitalize(),
                "post_date": datehelper(ele.formatted_postdate),
                "media": post_media_len,
                "length": ele.numeric_duration,
                "responsetype": ele.responsetype.capitalize(),
                "price": "Free" if ele._post.price == 0 else f"{ele._post.price:.2f}",
                "post_id": ele.post_id,
                "media_id": ele.id,
                "text": ele.post.db_sanitized_text,
                # not columns; where the file went, if it was downloaded
                "directory": directory,
                "filename": filename,
                # what its type_options entry is looked up by, as a download does
                "type_keys": media_type_keys(ele),
            }
        )

    ROWS = ROWS or []
    ROWS.extend(out)

    POST_ROWS = POST_ROWS or []
    posts_list = list(getattr(collection, "posts", None) or [])
    try:
        posts_list = sorted(posts_list, key=lambda x: undated_first(x.date), reverse=True)
    except Exception:
        pass
    POST_ROWS.extend(
        build_post_centric_rows(
            posts_list, username=username, model_id=model_id, start_index=len(POST_ROWS) + 1
        )
    )
