import asyncio
import inspect
import logging
import queue
import re
import threading
import time
import traceback

import arrow

import ofscraper.api.archive as archived
import ofscraper.api.highlights as highlights
import ofscraper.api.labels as labels
import ofscraper.api.messages as messages_
import ofscraper.api.paid as paid_
import ofscraper.api.pinned as pinned
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.classes.table.table as table
import ofscraper.db.operations as operations
import ofscraper.download.downloadnormal as downloadnormal
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.settings as settings
import ofscraper.utils.system.network as network
from ofscraper.classes.table.row_names import row_names_all
from ofscraper.db.operations_.media import batch_mediainsert, get_media_ids_downloaded
from ofscraper.download.shared.utils.text import textDownloader
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
console = console_.get_shared_console()

ROWS = []
ALL_MEDIA = {}
MEDIA_KEY = ["id", "postid", "username"]


def process_download_cart():
    while True:
        if table.row_queue.empty():
            time.sleep(10)
            continue
        try:
            process_item()
        except Exception:
            # handle getting new downloads
            None


def process_item():
    global app
    if process_download_cart.counter == 0:
        if not network.check_cdm():
            log.info("error was raised by cdm checker\ncdm will not be check again\n\n")
        else:
            log.info("cdm checker was fine\ncdm will not be check again\n\n")
    process_download_cart.counter = process_download_cart.counter + 1
    log.info("Getting items from cart")
    try:
        row, key = table.row_queue.get()
    except Exception as E:
        log.error(f"Error getting item from queue: {E}")
        return
    for count, _ in enumerate(range(0, 2)):
        try:
            username = row[list(row_names_all()).index("username")].plain
            post_id = int(row[list(row_names_all()).index("post_id")].plain)
            media_id = int(row[list(row_names_all()).index("media_id")].plain)
            media = ALL_MEDIA.get(
                "_".join(map(lambda x: str(x), [media_id, post_id, username]))
            )
            if not media:
                raise Exception(f"No data for {media_id}_{post_id}_{username}")
            log.info(f"Added url {media.url or media.mpd}")
            log.info("Sending URLs to OF-Scraper")
            selector.set_data_all_subs_dict(username)
            post = media.post
            if settings.get_mediatypes() == ["Text"]:
                textDownloader(post, username=username)
            elif len(settings.get_mediatypes()) > 1:
                model_id = media.post.model_id
                username = media.post.username
                log.info(
                    f"Downloading individual media ({media.filename}) to disk for {username}"
                )
                operations.table_init_create(model_id=model_id, username=username)
                textDownloader(post, username=username)
                values = downloadnormal.process_dicts(username, model_id, [media])
                if values is None or values[-1] == 1:
                    raise Exception("Download is marked as skipped")
            else:
                raise Exception("Issue getting download")

            log.info("Download Finished")
            table.app.update_cell(key, "download_cart", "[downloaded]")
            break
        except Exception as E:
            if count == 1:
                table.app.update_cell(key, "download_cart", "[failed]")
                raise E
            log.info("Download Failed Refreshing data")
            data_refill(media_id, post_id, username, model_id)
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    if table.row_queue.empty():
        log.info("Download cart is currently empty")


@run
async def data_refill(media_id, post_id, target_name, model_id):
    args = read_args.retriveArgs()
    if args.command == "msg_check":
        reset_message_set(model_id)
        retriver = message_check_retriver
    elif args.command == "paid_check":
        reset_paid_set(model_id)
        retriver = purchase_check_retriver
    elif args.command == "story_check":
        retriver = stories_check_retriver
    elif args.command == "post_check":
        reset_time_line_cache(model_id)
        retriver = post_check_retriver
    else:
        return
    async for username, model_id, final_post_array in retriver():
        if any(
            x.id == media_id and x.postid == post_id and x.username == target_name
            for x in await process_post_media(username, model_id, final_post_array)
        ):
            break


def checker():
    args = read_args.retriveArgs()
    if args.command == "post_check":
        post_checker()
    elif args.command == "msg_check":
        message_checker()
    elif args.command == "paid_check":
        purchase_checker()
    elif args.command == "story_check":
        stories_checker()


def post_checker():
    with stdout.lowstdout():
        post_check_runner()
    start_helper()


@run
async def post_check_runner():
    async for user_name, model_id, final_post_array in post_check_retriver():
        await process_post_media(user_name, model_id, final_post_array)
        await operations.make_changes_to_content_tables(
            final_post_array, model_id=model_id, username=user_name
        )
        await row_gather(user_name, model_id, paid=True)


@run
async def post_check_retriver():
    user_dict = {}
    links = list(url_helper())
    async with sessionManager.sessionManager(
        backend="httpx",
        sem=constants.getattr("API_REQ_CHECK_MAX"),
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        for ele in links:
            name_match = re.search(
                f"onlyfans.com/({constants.getattr('USERNAME_REGEX')}+$)", ele
            )
            name_match2 = re.search(f"^{constants.getattr('USERNAME_REGEX')}+$", ele)
            user_name = None
            model_id = None
            timeline_data = []
            labels_data = []
            pinned_data = []
            archived_data = []

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
                areas = read_args.retriveArgs().check_area
                await operations.table_init_create(
                    username=user_name, model_id=model_id
                )
                if "Timeline" in areas:
                    oldtimeline = cache.get(f"timeline_check_{model_id}", default=[])
                    if len(oldtimeline) > 0 and not read_args.retriveArgs().force:
                        timeline_data = oldtimeline
                    else:
                        timeline_data = await timeline.get_timeline_posts(
                            model_id, user_name, forced_after=0, c=c
                        )
                        cache.set(
                            f"timeline_check_{model_id}",
                            timeline_data,
                            expire=constants.getattr("THREE_DAY_SECONDS"),
                        )
                if "Archived" in areas:
                    oldarchive = cache.get(f"archived_check_{model_id}", default=[])
                    if len(oldarchive) > 0 and not read_args.retriveArgs().force:
                        archived_data = oldarchive
                    else:
                        archived_data = await archived.get_archived_posts(
                            model_id, user_name, forced_after=0, c=c
                        )
                        cache.set(
                            f"archived_check_{model_id}",
                            archived_data,
                            expire=constants.getattr("THREE_DAY_SECONDS"),
                        )
                if "Pinned" in areas:
                    oldpinned = cache.get(f"pinned_check_{model_id}", default=[])
                    if len(oldpinned) > 0 and not read_args.retriveArgs().force:
                        pinned_data = oldpinned
                    else:
                        pinned_data = await pinned.get_pinned_posts(model_id, c=c)
                        cache.set(
                            f"pinned_check_{model_id}",
                            pinned_data,
                            expire=constants.getattr("THREE_DAY_SECONDS"),
                        )
                if "Labels" in areas:
                    oldlabels = cache.get(f"labels_check_{model_id}", default=[])
                    if len(oldlabels) > 0 and not read_args.retriveArgs().force:
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
                            post for label in labels_resp for post in label["posts"]
                        ]
                        cache.set(
                            f"labels_check_{model_id}",
                            labels_data,
                            expire=constants.getattr("THREE_DAY_SECONDS"),
                        )
                all_post_data = list(
                    map(
                        lambda x: posts_.Post(x, model_id, user_name),
                        pinned_data + archived_data + labels_data + timeline_data,
                    )
                )
                cache.close()
                yield user_name, model_id, all_post_data
        # individual links
        for ele in list(
            filter(
                lambda x: re.search(
                    f"onlyfans.com/{constants.getattr('NUMBER_REGEX')}+/{constants.getattr('USERNAME_REGEX')}+$",
                    x,
                ),
                links,
            )
        ):
            name_match = re.search(f"/({constants.getattr('USERNAME_REGEX')}+$)", ele)
            num_match = re.search(f"/({constants.getattr('NUMBER_REGEX')}+)", ele)
            if name_match and num_match:
                user_name = name_match.group(1)
                model_id = profile.get_id(user_name)
                post_id = num_match.group(1)
                log.info(f"Getting individual link for {user_name}")
                resp = timeline.get_individual_post(post_id)
                data = list(map(lambda x: posts_.Post(x, model_id, user_name), resp))
                yield user_name, model_id, data


def reset_data():
    # clean up args once check modes are ready to launch
    args = read_args.retriveArgs()
    argdict = vars(args)
    if argdict.get("username"):
        read_args.retriveArgs().usernames = None
    write_args.setArgs(args)


def set_count(ROWS):
    for count, ele in enumerate(ROWS):
        ele[0] = count + 1


def start_helper():
    global ROWS
    reset_data()
    set_count(ROWS)
    network.check_cdm()
    thread_starters(ROWS)


def message_checker():
    with stdout.lowstdout():
        message_checker_runner()
    start_helper()


@run
async def message_checker_runner():
    async for user_name, model_id, final_post_array in message_check_retriver():
        await process_post_media(user_name, model_id, final_post_array)
        await operations.make_changes_to_content_tables(
            final_post_array, model_id=model_id, username=user_name
        )
        await row_gather(user_name, model_id, paid=True)


async def message_check_retriver():
    links = list(url_helper())
    async with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        for item in links:
            num_match = re.search(
                f"({constants.getattr('NUMBER_REGEX')}+)", item
            ) or re.search(f"^({constants.getattr('NUMBER_REGEX')}+)$", item)
            name_match = re.search(f"^{constants.getattr('USERNAME_REGEX')}+$", item)
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
                oldmessages = cache.get(f"message_check_{model_id}", default=[])
                log.debug(f"Number of messages in cache {len(oldmessages)}")

                if len(oldmessages) > 0 and not read_args.retriveArgs().force:
                    messages = oldmessages
                else:
                    messages = await messages_.get_messages(
                        model_id, user_name, forced_after=0, c=c
                    )
                    cache.set(
                        f"message_check_{model_id}",
                        messages,
                        expire=constants.getattr("THREE_DAY_SECONDS"),
                    )
                    cache.close()
                message_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), messages)
                )
                await operations.make_messages_table_changes(
                    message_posts_array, model_id=model_id, username=user_name
                )

                oldpaid = cache.get(f"purchased_check_{model_id}", default=[]) or []
                paid = None
                # paid content
                if len(oldpaid) > 0 and not read_args.retriveArgs().force:
                    paid = oldpaid
                else:
                    paid = await paid_.get_paid_posts(model_id, user_name, c=c)
                    cache.set(
                        f"purchased_check_{model_id}",
                        paid,
                        expire=constants.getattr("THREE_DAY_SECONDS"),
                    )
                    cache.close()
                paid_posts_array = list(
                    map(lambda x: posts_.Post(x, model_id, user_name), paid)
                )
                final_post_array = paid_posts_array + message_posts_array
                yield user_name, model_id, final_post_array


def purchase_checker():
    with stdout.lowstdout():
        purchase_checker_runner()
    start_helper()


@run
async def purchase_checker_runner():
    async for user_name, model_id, final_post_array in purchase_check_retriver():
        await process_post_media(user_name, model_id, final_post_array)
        await operations.make_changes_to_content_tables(
            final_post_array, model_id=model_id, username=user_name
        )
        await row_gather(user_name, model_id, paid=True)


@run
async def purchase_check_retriver():
    user_dict = {}
    auth_requests.make_headers()
    async with sessionManager.sessionManager(
        backend="httpx",
        sem=constants.getattr("API_REQ_CHECK_MAX"),
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        for name in read_args.retriveArgs().check_usernames:
            user_name = profile.scrape_profile(name)["username"]
            model_id = name if name.isnumeric() else profile.get_id(user_name)
            user_dict[model_id] = user_dict.get(model_id, [])

            await operations.table_init_create(model_id=model_id, username=user_name)

            oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
            paid = None

            if len(oldpaid) > 0 and not read_args.retriveArgs().force:
                paid = oldpaid
            elif user_name == constants.getattr("DELETED_MODEL_PLACEHOLDER"):
                paid_user_dict = await paid_.get_all_paid_posts()
                seen = set()
                paid = [
                    post
                    for post in paid_user_dict.get(str(model_id), [])
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
            else:
                paid = await paid_.get_paid_posts(model_id, user_name, c=c)
                cache.set(
                    f"purchased_check_{model_id}",
                    paid,
                    expire=constants.getattr("THREE_DAY_SECONDS"),
                )
                cache.close()
            posts_array = list(map(lambda x: posts_.Post(x, model_id, user_name), paid))
            yield user_name, model_id, posts_array


def stories_checker():
    with stdout.lowstdout():
        stories_checker_runner()
    start_helper()


@run
async def stories_checker_runner():
    async for user_name, model_id, final_post_array in stories_check_retriver():
        await process_post_media(user_name, model_id, final_post_array)
        await operations.make_changes_to_content_tables(
            final_post_array, model_id=model_id, username=user_name
        )
        await row_gather(user_name, model_id, paid=True)


@run
async def stories_check_retriver():
    user_dict = {}
    async with sessionManager.sessionManager(
        backend="httpx",
        sem=constants.getattr("API_REQ_CHECK_MAX"),
        retries=constants.getattr("API_CHECK_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        for user_name in read_args.retriveArgs().check_usernames:
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
    out.extend(read_args.retriveArgs().file or [])
    out.extend(read_args.retriveArgs().url or [])
    return map(lambda x: x.strip(), out)


@run
async def process_post_media(username, model_id, posts_array):
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
    temp = []
    [temp.extend(ele.all_media) for ele in unduped]
    await batch_mediainsert(
        temp,
        model_id=model_id,
        username=username,
        downloaded=False,
    )
    new_media = {
        "_".join([str(getattr(ele, key)) for key in MEDIA_KEY]): ele for ele in temp
    }
    ALL_MEDIA.update(new_media)
    return list(new_media.values())


@run
async def get_downloaded(user_name, model_id, paid=False):
    downloaded = {}

    await operations.table_init_create(model_id=model_id, username=user_name)
    paid = await get_paid_ids(model_id, user_name) if paid else []
    [
        downloaded.update({ele: downloaded.get(ele, 0) + 1})
        for ele in get_media_ids_downloaded(model_id=model_id, username=user_name)
        + paid
    ]

    return downloaded


@run
async def get_paid_ids(model_id, user_name):
    oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
    paid = None

    if len(oldpaid) > 0 and not read_args.retriveArgs().force:
        paid = oldpaid
    else:
        async with sessionManager.sessionManager(
            backend="httpx",
            sem=constants.getattr("API_REQ_CHECK_MAX"),
            retries=constants.getattr("API_CHECK_NUM_TRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
            new_request_auth=True,
        ) as c:
            paid = await paid_.get_paid_posts(model_id, user_name, c=c)
            cache.set(
                f"purchase_check_{model_id}",
                paid,
                expire=constants.getattr("THREE_DAY_SECONDS"),
            )
    media = await process_post_media(user_name, model_id, paid)
    media = list(filter(lambda x: x.canview is True, media))
    return list(map(lambda x: x.id, media))


def thread_starters(ROWS_):
    worker_thread = threading.Thread(target=process_download_cart, daemon=True)
    worker_thread.start()
    process_download_cart.counter = 0
    start_table(ROWS_)


def start_table(ROWS_):
    global app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ROWS = ROWS_
    app = table.app(
        table_data=ROWS, mutex=threading.Lock(), mediatype=init_media_type_helper()
    )


def texthelper(text):
    text = text or ""
    text = inspect.cleandoc(text)
    text = re.sub(" +$", "", text)
    text = re.sub("^ +", "", text)
    text = re.sub("<[^>]*>", "", text)
    text = (
        text
        if len(text) < constants.getattr("TABLE_STR_MAX")
        else f"{text[:constants.getattr('TABLE_STR_MAX')]}..."
    )
    return text


def unlocked_helper(ele):
    return ele.canview


def datehelper(date):
    if date == "None":
        return "Probably Deleted"
    return date


def times_helper(ele, mediadict, downloaded):
    return max(len(mediadict.get(ele.id, [])), downloaded.get(ele.id, 0))


def checkmarkhelper(ele):
    return "[]" if unlocked_helper(ele) else "Not Unlocked"


async def row_gather(username, model_id, paid=False):
    # fix tex
    global ROWS
    downloaded = await get_downloaded(username, model_id, paid=paid)

    mediadict = {}
    [
        mediadict.update({ele.id: mediadict.get(ele.id, []) + [ele]})
        for ele in list(filter(lambda x: x.canview, ALL_MEDIA.values()))
    ]
    out = []

    media_sorted = sorted(
        ALL_MEDIA.values(), key=lambda x: arrow.get(x.date), reverse=True
    )
    for count, ele in enumerate(media_sorted):
        out.append(
            {
                "index": count,
                "number": None,
                "download_cart": checkmarkhelper(ele),
                "username": username,
                "downloaded": ele.id in downloaded
                or cache.get(ele.postid) is not None
                or cache.get(ele.filename) is not None,
                "unlocked": unlocked_helper(ele),
                "times_detected": times_helper(ele, mediadict, downloaded),
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


def init_media_type_helper():
    args = read_args.retriveArgs()
    mediatype = args.mediatype
    args.mediatype = None
    write_args.setArgs(args)
    return mediatype


def reset_time_line_cache(model_id):
    cache.set(f"timeline_check_{model_id}", [])
    cache.set(f"archived_check_{model_id}", [])
    cache.set(f"labels_check_{model_id}", [])
    cache.set(f"pinned_check_{model_id}", [])
    cache.close()


def reset_message_set(model_id):
    cache.set(f"message_check_{model_id}", [])
    cache.set(f"purchased_check_{model_id}", [])
    cache.close()


def reset_paid_set(model_id):
    cache.set(f"purchased_check_{model_id}", [])
    cache.close()
