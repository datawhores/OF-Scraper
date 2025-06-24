import asyncio
import copy
import inspect
import logging
import re
import threading
import time
import traceback
from collections import defaultdict

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
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.settings as settings
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.console as console_
import ofscraper.utils.env.env as env
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.system.network as network
from ofscraper.data.api.common.check import read_check, reset_check, set_check
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.commands.utils.strings import check_str
from ofscraper.db.operations import make_changes_to_content_tables
from ofscraper.db.operations_.media import (
    batch_mediainsert,
    get_media_post_ids_downloaded,
)
from ofscraper.utils.checkers import check_auth
from ofscraper.utils.context.run_async import run
from ofscraper.main.close.final.final_user import post_user_script
from ofscraper.main.close.final.final import final
import ofscraper.main.manager as manager
import ofscraper.filters.media.main as filters
from ofscraper.commands.scraper.actions.download.download import process_dicts
from rich.text import Text


log = logging.getLogger("shared")
console = console_.get_shared_console()

ROWS = []
ALL_MEDIA = {}
MEDIA_KEY = ["id", "postid", "username"]


def process_download_cart():
    global cart_dict
    while True:
        try:
            cart_dict = {}
            if app.row_queue.empty():
                continue

            while not app.row_queue.empty():
                try:
                    process_item()
                except Exception as _:
                    # handle getting new downloads
                    None
            if len(cart_dict.keys()) > 0:
                for val in cart_dict.values():
                    post_user_script(val["userdata"], val["media"], val["post"])
                results = ["check cart results"] + list(
                    map(lambda x: x["results"], cart_dict.values())
                )
                final(normal_data=results)
            time.sleep(5)
        except Exception as e:
            log.traceback_(f"Error in process_item: {e}")
            log.traceback_(f"Error in process_item: {traceback.format_exc()}")
            continue


def process_item():
    if process_download_cart.counter == 0:
        if not network.check_cdm():
            log.info("error was raised by cdm checker\ncdm will not be check again\n\n")
        else:
            log.info("cdm checker was fine\ncdm will not be check again\n\n")
    process_download_cart.counter = process_download_cart.counter + 1
    log.info("Getting items from cart")
    try:
        key, row = app.row_queue.get()
    except Exception as E:
        log.debug(f"Error getting item from queue: {E}")
        return
    for count, _ in enumerate(range(0, 2)):
        try:
            username = row["username"]
            post_id = int(row["post_id"])
            media_id = int(row["media_id"])
            media = ALL_MEDIA.get(
                "_".join(map(lambda x: str(x), [media_id, post_id, username]))
            )
            if not media:
                raise Exception(f"No data for {media_id}_{post_id}_{username}")
            log.info(f"Added url {media.url or media.mpd}")
            log.info("Sending URLs to OF-Scraper")
            manager.Manager.model_manager.set_data_all_subs_dict(username)
            post = media.post
            model_id = media.post.model_id
            username = media.post.username

            log.info(
                f"Downloading individual media ({media.filename}) to disk for {username}"
            )
            operations.table_init_create(model_id=model_id, username=username)

            output, values = process_dicts(username, model_id, [media], [post])
            if values is None or values[-1] == 1:
                raise Exception("Download is marked as failed")
            elif values[-2] == 1:
                log.info("Download Skipped")
                app.app.table.update_cell_at_key(
                    key, "download_cart", Text("[skipped]", style="bold bright_yellow")
                )

            else:
                log.info("Download Finished")
                update_globals(model_id, username, post, media, output)
                app.app.table.update_cell_at_key(
                    key, "download_cart", Text("[downloaded]", style="bold green")
                )
                break
        except Exception as E:
            if count == 1:
                app.app.table.update_cell_at_key(
                    key, "download_cart", Text("[failed]", style="bold red")
                )
                raise E
            log.info("Download Failed Refreshing data")
            data_refill(media_id, post_id, username, model_id)
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    if app.row_queue.empty():
        log.info("Download cart is currently empty")


def update_globals(model_id, username, post, media, values):
    global cart_dict
    cart_dict.setdefault(
        model_id,
        {
            "post": [],
            "media": [],
            "username": username,
            "model_id": model_id,
            "userdata": manager.Manager.model_manager.get_model(username),
            "results": values,
        },
    )
    cart_dict[model_id]["post"].extend([post])
    cart_dict[model_id]["media"].extend([media])


@run
async def data_refill(media_id, post_id, target_name, model_id):
    if settings.get_settings().command == "msg_check":
        reset_message_set(model_id)
        retriver = message_check_retriver
    elif settings.get_settings().command == "paid_check":
        reset_paid_set(model_id)
        retriver = purchase_check_retriver
    elif settings.get_settings().command == "story_check":
        retriver = stories_check_retriver
    elif settings.get_settings().command == "post_check":
        reset_time_line_cache(model_id)
        retriver = post_check_retriver
    else:
        return
    async for username, model_id, final_post_array in retriver():
        for x in await process_post_media(username, model_id, final_post_array):
            ALL_MEDIA.update({"_".join([str(getattr(x, key)) for key in MEDIA_KEY]): x})


def allow_check_dupes():
    args = read_args.retriveArgs()
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
    args = read_args.retriveArgs()
    args.after = 0
    settings.update_args(args)


def post_checker():
    post_check_runner()
    start_helper()


@run
async def post_check_runner():
    async for user_name, model_id, final_post_array in post_check_retriver():
        with progress_utils.setup_api_split_progress_live(revert=True):
            progress_updater.update_activity_task(
                description=check_str.format(
                    username=user_name, activity="Timeline posts"
                )
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


@run
async def post_check_retriver():
    user_dict = {}
    links = list(url_helper())
    async with manager.Manager.aget_ofsession(
       
        sem_count=env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for ele in links:
            name_match = re.search(
                f"onlyfans.com/({env.getattr('USERNAME_REGEX')}+$)", ele
            )
            name_match2 = re.search(f"^{env.getattr('USERNAME_REGEX')}+$", ele)
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
                    if len(oldtimeline) > 0 and not settings.get_settings().force:
                        timeline_data = oldtimeline
                    else:
                        timeline_data = await timeline.get_timeline_posts(
                            model_id, user_name, c=c
                        )
                        set_check(timeline_data, model_id, timeline.API)
                if "Archived" in areas:
                    oldarchive = read_check(model_id, archived.API)
                    if len(oldarchive) > 0 and not settings.get_settings().force:
                        archived_data = oldarchive
                    else:
                        archived_data = await archived.get_archived_posts(
                            model_id, user_name, c=c
                        )
                        set_check(archived_data, model_id, archived.API)

                if "Pinned" in areas:
                    oldpinned = read_check(model_id, pinned.API)
                    if len(oldpinned) > 0 and not settings.get_settings().force:
                        pinned_data = oldpinned
                    else:
                        pinned_data = await pinned.get_pinned_posts(model_id, c=c)
                        set_check(pinned_data, model_id, pinned.API)

                if "Labels" in areas:
                    oldlabels = read_check(model_id, labels.API)
                    if len(oldlabels) > 0 and not settings.get_settings().force:
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
                    if len(oldstreams) > 0 and not settings.get_settings().force:
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
                    f"onlyfans.com/{env.getattr('NUMBER_REGEX')}+/{env.getattr('USERNAME_REGEX')}+$",
                    x,
                ),
                links,
            )
        ):
            name_match = re.search(f"/({env.getattr('USERNAME_REGEX')}+$)", ele)
            num_match = re.search(f"/({env.getattr('NUMBER_REGEX')}+)", ele)
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
    args = read_args.retriveArgs()
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
        with progress_utils.setup_api_split_progress_live(revert=True):
            progress_updater.update_activity_task(
                description=check_str.format(username=user_name, activity="Messages")
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


async def message_check_retriver():
    links = list(url_helper())
    async with manager.Manager.aget_ofsession(
       
    ) as c:
        for item in links:
            num_match = re.search(
                f"({env.getattr('NUMBER_REGEX')}+)", item
            ) or re.search(f"^({env.getattr('NUMBER_REGEX')}+)$", item)
            name_match = re.search(f"^{env.getattr('USERNAME_REGEX')}+$", item)
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

                if len(oldmessages) > 0 and not settings.get_settings().force:
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
                if len(oldpaid) > 0 and not settings.get_settings().force:
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
        with progress_utils.setup_api_split_progress_live(revert=True):
            progress_updater.update_activity_task(
                description=check_str.format(
                    username=user_name, activity="Purchased posts"
                )
            )
            await process_post_media(user_name, model_id, final_post_array)
            await make_changes_to_content_tables(
                final_post_array, model_id=model_id, username=user_name
            )
            await row_gather(user_name, model_id)


@run
async def purchase_check_retriver():
    user_dict = {}
    auth_requests.make_headers()
    async with manager.Manager.aget_ofsession(
       
        sem_count=env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        for name in settings.get_settings().check_usernames:
            user_name = profile.scrape_profile(name)["username"]
            model_id = name if name.isnumeric() else profile.get_id(user_name)
            user_dict[model_id] = user_dict.get(model_id, [])

            await operations.table_init_create(model_id=model_id, username=user_name)

            oldpaid = read_check(model_id, paid_.API)
            paid = None

            if len(oldpaid) > 0 and not settings.get_settings().force:
                paid = oldpaid
            elif user_name == env.getattr("DELETED_MODEL_PLACEHOLDER"):
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
        with progress_utils.setup_api_split_progress_live(revert=True):
            progress_updater.update_activity_task(
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
async def stories_check_retriver():
    user_dict = {}
    async with manager.Manager.aget_ofsession(
       
        sem_count=env.getattr("API_REQ_CHECK_MAX"),
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
    media = await insert_media(username, model_id, posts_array)
    media = filter_media(username, model_id, media)
    new_media = {
        "_".join([str(getattr(ele, key)) for key in MEDIA_KEY]): ele for ele in media
    }
    ALL_MEDIA.update(new_media)
    return list(new_media.values())


async def insert_media(username, model_id, posts_array):
    posts_array = list(
        map(
            lambda x: (
                posts_.Post(x, model_id, username)
                if not isinstance(x, posts_.Post)
                else x
            ),
            posts_array,
        )
    )
    seen = set()
    unduped = [
        post
        for post in posts_array
        if (post.id, post.username) not in seen
        and not seen.add((post.id, post.username))
    ]
    media = []
    [media.extend(ele.all_media) for ele in unduped]

    await batch_mediainsert(
        media,
        model_id=model_id,
        username=username,
        downloaded=False,
    )
    return media


def filter_media(username, model_id, media):

    return filters.filterCheckMode(media, username, model_id)


@run
async def get_paid_ids(model_id, user_name):
    oldpaid = read_check(model_id, paid_.API)
    paid = None

    if len(oldpaid) > 0 and not settings.get_settings().force:
        paid = oldpaid
    else:
        async with manager.Manager.aget_ofsession(
            sem_count=env.getattr("API_REQ_CHECK_MAX")
        ) as c:
            paid = await paid_.get_paid_posts(model_id, user_name, c=c)
            set_check(paid, model_id, paid_.API)

    media = await process_post_media(user_name, model_id, paid)
    media = list(filter(lambda x: x.canview is True, media))
    return list(map(lambda x: x.id, media))


def thread_starters(ROWS_):
    worker_thread = threading.Thread(target=process_download_cart, daemon=True)
    worker_thread.start()
    process_download_cart.counter = 0
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
        if len(text) < env.getattr("TABLE_STR_MAX")
        else f"{text[:env.getattr('TABLE_STR_MAX')]}..."
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


def times_helper(ele, mediadict):
    matching = copy.copy(mediadict.get(ele.id, set()))
    matching.discard(ele.postid)
    return list(matching)


def checkmarkhelper(ele):
    return "[]" if unlocked_helper(ele) else "Not Unlocked"


def get_media_dict(downloaded):
    mediadict = defaultdict(lambda: set())
    [
        mediadict[ele.id].add(ele.postid)
        for ele in list(filter(lambda x: x.canview, ALL_MEDIA.values()))
    ]
    [mediadict[ele[0]].add(ele[1]) for ele in list(downloaded)]
    return mediadict


async def row_gather(username, model_id):
    global ROWS
    downloaded = set(
        get_media_post_ids_downloaded(model_id=model_id, username=username)
    )
    media_dict = get_media_dict(downloaded)
    out = []
    for count, ele in enumerate(
        sorted(ALL_MEDIA.values(), key=lambda x: arrow.get(x.date), reverse=True)
    ):
        out.append(
            {
                "index": count + 1,
                "number": count + 1,
                "download_cart": checkmarkhelper(ele),
                "username": username,
                "downloaded": (ele.id, ele.postid) in downloaded,
                "unlocked": unlocked_helper(ele),
                "download_type": download_type_helper(ele),
                "other_posts_with_media": times_helper(ele, media_dict),
                "post_media_count": len(ele._post.post_media),
                "mediatype": ele.mediatype,
                "post_date": datehelper(ele.formatted_postdate),
                "media": len(ele._post.post_media),
                "length": ele.numeric_duration,
                "responsetype": ele.responsetype,
                "price": (
                    "Free" if ele._post.price == 0 else "{:.2f}".format(ele._post.price)
                ),
                "post_id": ele.postid,
                "media_id": ele.id,
                "text": ele.post.db_sanitized_text,
            }
        )
    ROWS = ROWS or []
    ROWS.extend(out)


def reset_time_line_cache(model_id):
    reset_check(model_id, timeline.API)
    reset_check(model_id, archived.API)
    reset_check(model_id, labels.API)
    reset_check(model_id, pinned.API)


def reset_message_set(model_id):
    reset_check(model_id, messages_.API)
    reset_check(model_id, paid_.API)


def reset_paid_set(model_id):
    reset_check(model_id, paid_.API)
