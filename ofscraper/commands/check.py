import asyncio
import inspect
import logging
import re
import threading
import time
import traceback
from copy import deepcopy
from functools import partial

from collections import defaultdict
from rich.text import Text


import arrow

import ofscraper.data.api.archive as archived
import ofscraper.data.api.highlights as highlights
import ofscraper.data.api.labels as labels
import ofscraper.data.api.messages as messages_
import ofscraper.data.api.paid as paid_
import ofscraper.data.api.pinned as pinned
import ofscraper.data.api.profile as profile
import ofscraper.data.api.streams as streams
import ofscraper.data.api.timeline as timeline
import ofscraper.classes.of.posts as posts_
import ofscraper.classes.table.app as app
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.console as console_
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.system.network as network
from ofscraper.data.api.common.check import read_check, set_check
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.commands.utils.strings import check_str
from ofscraper.db.operations import make_changes_to_content_tables
from ofscraper.db.operations_.media import (
    batch_mediainsert,
    get_media_post_ids_downloaded,
)
from ofscraper.utils.checkers import check_auth
from ofscraper.utils.context.run_async import run
from ofscraper.scripts.after_download_action_script import after_download_action_script
import ofscraper.managers.manager as manager
from ofscraper.commands.scraper.actions.download.download import process_dicts
import ofscraper.managers.manager as manager
from ofscraper.managers.postcollection import PostCollection
from ofscraper.main.close.final.final import final_action


log = logging.getLogger("shared")
console = console_.get_shared_console()


ALL_MEDIA = {}
ROWS = {}
MEDIA_KEY = ["id", "postid", "username"]
check_user_dict = defaultdict(dict)


def process_download_queue():
    """
    Orchestrator function that processes the entire download queue in batches grouped by user.
    """
    while True:
        if app.row_queue.empty():
            time.sleep(1)
            continue
        user_cart = defaultdict(lambda: {"posts": [], "media": [], "rows": []})
        while not app.row_queue.empty():
            try:
                key, row_data = app.row_queue.get()
                media_item, post_item, username, model_id = _get_data_from_row(row_data)

                # Append all necessary data for later processing
                user_cart[model_id]["posts"].append(post_item)
                user_cart[model_id]["media"].append(media_item)
                user_cart[model_id]["rows"].append((key, row_data))
                user_cart[model_id]["username"] = username  # Store username once

            except Exception as e:
                log.error(f"Error processing row from queue: {e}")
                log.traceback_(traceback.format_exc())

        # 2. PROCESS: Loop through each user's batch and process their items
        for model_id, data in user_cart.items():
            username = data["username"]
            log.info(f"Processing download batch for user: {username}")
            try:
                # Pass the user's entire batch to the processing function
                _process_user_batch(
                    username, model_id, data["media"], data["posts"], data["rows"]
                )

                # Run after-actions for this user
                after_download_action_script(username, data["media"], data["posts"])
                manager.Manager.model_manager.mark_as_processed(
                    username, activity="download"
                )
                manager.Manager.stats_manager.update_and_print_stats(
                    username, "download", data["media"]
                )

            except Exception as e:
                log.error(
                    f"An error occurred while processing the batch for {username}."
                )
                log.traceback_(e)

        # 3. FINAL CLEANUP: Now that all batches are processed, clear the queue
        final_action()
        manager.Manager.model_manager.clear_queue("download")
        manager.Manager.stats_manager.clear_activity_stats("download")
        log.info("Download processing complete. Waiting for new items...")


def _get_data_from_row(row: dict):
    """
    Takes a row dictionary and returns fresh, deep copies of the
    corresponding data objects to prevent state issues between loops.
    """
    username = row["username"]
    media_id = int(row["media_id"])

    manager.Manager.model_manager.add_models(username, activity="download")
    model_obj = manager.Manager.model_manager.get_model(username)
    if not model_obj:
        raise Exception(f"Could not find model for username: {username}")

    # Find the original, cached media object
    cached_media = check_user_dict[model_obj.id]["collection"].find_media_item(media_id)
    if not cached_media:
        raise Exception(f"No media data found for media_id {media_id} from {username}")

    # Create fresh, deep copies to work with.
    # This ensures no state from a previous loop is carried over.
    fresh_media = deepcopy(cached_media)
    fresh_post = deepcopy(cached_media.post)

    # The rest of the system will now use these fresh, stateless copies
    return fresh_media, fresh_post, username, model_obj.id


def _process_user_batch(
    username: str, model_id: int, media_list: list, post_list: list, row_list: list
):
    """
    Processes all media items for a single user's batch.
    """
    if _process_user_batch.counter == 0:
        # Simplified CDM check
        log.info("Performing first-run CDM check...")
        if not network.check_cdm():
            log.info("CDM check raised an error. This check will not be repeated.")
        else:
            log.info("CDM check passed. This check will not be repeated.")
    _process_user_batch.counter += 1

    operations.table_init_create(model_id=model_id, username=username)

    for i, media in enumerate(media_list):
        key = row_list[i][0]  # Get the original key for UI updates
        post = post_list[i]

        log.info(f"Attempting to download: {media.filename} for {username}")

        # Retry logic for each item
        for attempt in range(2):  # 0 for first try, 1 for retry
            try:
                values = process_dicts(username, model_id, media, post)
                if values is None or values[-1] == 1:
                    raise Exception("Download failed based on process_dicts result")

                # Success cases
                if values[-2] == 1:
                    log.info(f"Download skipped: {media.filename}")
                    app.app.table.update_cell_at_key(
                        key,
                        "download_cart",
                        Text("[skipped]", style="bold bright_yellow"),
                    )
                else:
                    log.info(f"Download finished: {media.filename}")
                    app.app.table.update_cell_at_key(
                        key, "download_cart", Text("[downloaded]", style="bold green")
                    )

                break  # Exit retry loop on success

            except Exception as e:
                log.warning(f"Attempt {attempt + 1} failed for {media.filename}: {e}")
                if attempt == 0:  # If first attempt failed
                    log.info("Refreshing data and retrying...")
                    data_refill(model_id)
                    time.sleep(1)  # Small delay before retry
                else:  # If second attempt also failed
                    log.error(f"Download failed permanently for {media.filename}.")
                    app.app.table.update_cell_at_key(
                        key, "download_cart", Text("[failed]", style="bold red")
                    )


# Initialize counter on the function object
_process_user_batch.counter = 0


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
    async for username, model_id, final_post_array in retriver():
        await process_post_media(username, model_id, final_post_array)


def allow_check_dupes():
    args = settings.get_args()
    args.force_all = True
    settings.update_args(args)


def get_areas():
    return settings.get_settings().check_area


def checker():
    check_auth()
    allow_check_dupes()
    set_after_check_mode()
    try:
        if settings.get_settings().command == "post_check":
            post_checker()
        elif settings.get_settings().command == "msg_check":
            message_checker()
        elif settings.get_settings().command == "paid_check":
            purchase_checker()
        elif settings.get_settings().command == "story_check":
            stories_checker()
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


def set_after_check_mode():
    args = settings.get_args()
    args.after = 0
    settings.update_args(args)


def post_checker():
    post_check_runner()
    start_helper()


@run
async def post_check_runner():
    async for user_name, model_id, final_post_array in post_check_retriver():
        with progress_utils.setup_live("api"):
            progress_updater.activity.update_task(
                description=check_str.format(
                    username=user_name, activity="Timeline posts"
                ),
                visible=True,
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


@run
async def post_check_retriver(forced=False):
    user_dict = {}
    links = list(url_helper())
    if settings.get_settings().force:
        forced = True
    async with manager.Manager.aget_ofsession(
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

            if name_match:
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
            if user_dict.get(model_id) and model_id and user_name:
                areas = get_areas()
                await operations.table_init_create(
                    username=user_name, model_id=model_id
                )
                if "Timeline" in areas:
                    oldtimeline = read_check(model_id, timeline.API)
                    if len(oldtimeline) > 0 and not forced:
                        timeline_data = oldtimeline
                    else:
                        timeline_data = await timeline.get_timeline_posts(
                            model_id, user_name, c=c
                        )
                        set_check(timeline_data, model_id, timeline.API)
                if "Archived" in areas:
                    oldarchive = read_check(model_id, archived.API)
                    if len(oldarchive) > 0 and not forced:
                        archived_data = oldarchive
                    else:
                        archived_data = await archived.get_archived_posts(
                            model_id, user_name, c=c
                        )
                        set_check(archived_data, model_id, archived.API)

                if "Pinned" in areas:
                    oldpinned = read_check(model_id, pinned.API)
                    if len(oldpinned) > 0 and not forced:
                        pinned_data = oldpinned
                    else:
                        pinned_data = await pinned.get_pinned_posts(model_id, c=c)
                        set_check(pinned_data, model_id, pinned.API)

                if "Labels" in areas:
                    oldlabels = read_check(model_id, labels.API)
                    if len(oldlabels) > 0 and not forced:
                        labels_data = oldlabels
                    else:
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

                if "Streams" in areas:
                    oldstreams = read_check(model_id, streams.API)
                    if len(oldstreams) > 0 and not forced:
                        streams_data = oldstreams
                    else:
                        streams_resp = await streams.get_streams_posts(
                            model_id, user_name, c=c
                        )
                        streams_data = [
                            post
                            for streams in streams_resp
                            for post in streams.get("posts", [])
                        ]
                        set_check(streams_data, model_id, streams.API)

                await operations.make_post_table_changes(
                    all_posts=pinned_data
                    + archived_data
                    + labels_data
                    + timeline_data
                    + streams_data,
                    model_id=model_id,
                    username=user_name,
                )
                all_post_data = []
                for ele in [
                    pinned_data,
                    archived_data,
                    labels_data,
                    timeline_data,
                    streams_data,
                ]:
                    if ele == timeline_data:

                        all_post_data.append(
                            timeline.filter_timeline_post(
                                list(
                                    map(
                                        lambda x: posts_.Post(x, model_id, user_name),
                                        timeline_data,
                                    )
                                )
                            )
                        )
                    else:
                        all_post_data.append(
                            map(lambda x: posts_.Post(x, model_id, user_name), ele)
                        )

                all_post_data = list(
                    map(
                        lambda x: posts_.Post(x, model_id, user_name),
                        pinned_data
                        + archived_data
                        + labels_data
                        + timeline_data
                        + streams_data,
                    )
                )

                yield user_name, model_id, all_post_data
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
                post_id = num_match.group(1)
                log.info(f"Getting individual link for {user_name}")
                resp = get_individual_timeline_post(post_id)
                data = list(map(lambda x: posts_.Post(x, model_id, user_name), resp))
                yield user_name, model_id, data


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
    message_checker_runner()
    start_helper()


@run
async def message_checker_runner():
    async for user_name, model_id, final_post_array in message_check_retriver():
        with progress_utils.setup_live("api"):
            progress_updater.activity.update_task(
                description=check_str.format(username=user_name, activity="Messages"),
                visible=True,
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


async def message_check_retriver(forced=False):
    links = list(url_helper())
    if settings.get_settings().force:
        forced = True
    async with manager.Manager.aget_ofsession() as c:
        for item in links:
            num_match = re.search(
                f"({of_env.getattr('NUMBER_REGEX')}+)", item
            ) or re.search(f"^({of_env.getattr('NUMBER_REGEX')}+)$", item)
            name_match = re.search(f"^{of_env.getattr('USERNAME_REGEX')}+$", item)
            if num_match:
                model_id = num_match.group(1)
                user_name = profile.scrape_profile(model_id)["username"]
            elif name_match:
                user_name = name_match.group(0)
                model_id = profile.get_id(user_name)
            if model_id and user_name:
                log.info(f"Getting Messages/Paid content for {user_name}")
                await operations.table_init_create(
                    model_id=model_id, username=user_name
                )
                # messages
                messages = None
                oldmessages = read_check(model_id, messages_.API)
                log.debug(f"Number of messages in cache {len(oldmessages)}")

                if len(oldmessages) > 0 and not forced:
                    messages = oldmessages
                else:
                    messages = await messages_.get_messages(model_id, user_name, c=c)
                    set_check(messages, model_id, messages_.API)

                message_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), messages)
                )
                await operations.make_messages_table_changes(
                    message_posts_array, model_id=model_id, username=user_name
                )

                oldpaid = read_check(model_id, paid_.API) or []
                paid = None
                # paid content
                if len(oldpaid) > 0 and not forced:
                    paid = oldpaid
                else:
                    paid = await paid_.get_paid_posts(model_id, user_name, c=c)
                    set_check(paid, model_id, paid_.API)
                paid_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), paid)
                )
                final_post_array = paid_posts_array + message_posts_array
                yield user_name, model_id, final_post_array


def purchase_checker():
    purchase_checker_runner()
    start_helper()


@run
async def purchase_checker_runner():
    async for user_name, model_id, final_post_array in purchase_check_retriver():
        with progress_utils.setup_live("api"):
            progress_updater.activity.update_task(
                description=check_str.format(
                    username=user_name, activity="Purchased posts"
                ),
                visible=True,
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


@run
async def purchase_check_retriver(forced=False):
    user_dict = {}
    auth_requests.make_headers()
    if settings.get_settings().force:
        forced = True
    async with manager.Manager.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for name in settings.get_settings().check_usernames:
            user_name = profile.scrape_profile(name)["username"]
            model_id = name if name.isnumeric() else profile.get_id(user_name)
            user_dict[model_id] = user_dict.get(model_id, [])

            await operations.table_init_create(model_id=model_id, username=user_name)

            oldpaid = read_check(model_id, paid_.API)
            paid = None

            if len(oldpaid) > 0 and not forced:
                paid = oldpaid
            elif user_name == of_env.getattr("DELETED_MODEL_PLACEHOLDER"):
                paid_user_dict = await paid_.get_all_paid_posts()
                seen = set()
                paid = [
                    post
                    for post in paid_user_dict.get(str(model_id), [])
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
            else:
                paid = await paid_.get_paid_posts(model_id, user_name, c=c)
                set_check(paid, model_id, paid_.API)
            posts_array = list(map(lambda x: posts_.Post(x, model_id, user_name), paid))
            yield user_name, model_id, posts_array


def stories_checker():
    stories_checker_runner()
    start_helper()


@run
async def stories_checker_runner():
    async for user_name, model_id, final_post_array in stories_check_retriver():
        with progress_utils.setup_live("api"):
            progress_updater.activity.update_task(
                description=check_str.format(
                    username=user_name, activity="Stories posts"
                )
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


@run
async def stories_check_retriver(forced=False):
    user_dict = {}
    async with manager.Manager.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for user_name in settings.get_settings().check_usernames:
            user_name = profile.scrape_profile(user_name)["username"]
            model_id = profile.get_id(user_name)
            user_dict[model_id] = user_dict.get(user_name, [])
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


def url_helper():
    out = []
    out.extend(settings.get_settings().file or [])
    out.extend(settings.get_settings().url or [])
    return map(lambda x: x.strip(), out)


@run
async def process_post_media(username, model_id, posts_array):
    check_user_dict[model_id].setdefault(
        "collection", PostCollection(username=username, model_id=model_id)
    )
    collection = check_user_dict[model_id]["collection"]
    collection: PostCollection
    collection.add_posts(posts_array)
    media = collection.all_unique_media
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

    if len(oldpaid) > 0 and not settings.get_settings().force:
        paid = oldpaid
    else:
        async with manager.Manager.aget_ofsession(
            sem_count=of_env.getattr("API_REQ_CHECK_MAX")
        ) as c:
            paid = await paid_.get_paid_posts(model_id, user_name, c=c)
            set_check(paid, model_id, paid_.API)

    media = await process_post_media(user_name, model_id, paid)
    media = list(filter(lambda x: x.canview is True, media))
    return list(map(lambda x: x.id, media))


def thread_starters(ROWS_):
    worker_thread = threading.Thread(target=process_download_queue, daemon=True)
    worker_thread.start()
    start_table(ROWS_)


def start_table(ROWS_):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ROWS = ROWS_
    app.app(table_data=ROWS)


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
    return ele.canview


def download_type_helper(ele):
    if ele.mpd:
        return "protected"
    elif ele.url:
        return "normal"
    return "n/a"


def datehelper(date):
    if date == "None":
        return "Probably Deleted"
    return date


def checkmarkhelper(ele):
    return "[]" if unlocked_helper(ele) else "Not Unlocked"


async def row_gather(username, model_id):
    global ROWS
    downloaded = set(
        get_media_post_ids_downloaded(model_id=model_id, username=username)
    )
    collection = check_user_dict[model_id]["collection"]
    if not collection:
        raise Exception("No postcollection object found")
    media = collection.all_unique_media
    out = []
    for count, ele in enumerate(
        sorted(media, key=lambda x: arrow.get(x.date), reverse=True)
    ):
        out.append(
            {
                "index": count + 1,
                "number": count + 1,
                "download_cart": checkmarkhelper(ele),
                "username": username,
                "downloaded": (ele.id, ele.post_id) in downloaded,
                "unlocked": unlocked_helper(ele),
                "download_type": download_type_helper(ele),
                "other_posts_with_media": collection.posts_with_media_id(ele.id),
                "post_media_count": len(ele._post.post_media),
                "mediatype": ele.mediatype,
                "post_date": datehelper(ele.formatted_postdate),
                "media": len(ele._post.post_media),
                "length": ele.numeric_duration,
                "responsetype": ele.responsetype,
                "price": (
                    "Free" if ele._post.price == 0 else "{:.2f}".format(ele._post.price)
                ),
                "post_id": ele.post_id,
                "media_id": ele.id,
                "text": ele.post.db_sanitized_text,
            }
        )
    ROWS = ROWS or []
    ROWS.extend(out)
