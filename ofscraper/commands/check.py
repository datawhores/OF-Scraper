import asyncio
import logging
import queue
import re
import textwrap
import threading
import time

import arrow

import ofscraper.api.archive as archive
import ofscraper.api.highlights as highlights
import ofscraper.api.messages as messages_
import ofscraper.api.paid as paid_
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.classes.table as table
import ofscraper.commands.manual as manual
import ofscraper.db.operations as operations
import ofscraper.download.downloadnormal as downloadnormal
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.auth as auth
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
import ofscraper.utils.system.network as network

log = logging.getLogger("shared")
console = console_.get_shared_console()
ROW_NAMES = (
    "Number",
    "Download_Cart",
    "UserName",
    "Downloaded",
    "Unlocked",
    "Times_Detected",
    "Length",
    "Mediatype",
    "Post_Date",
    "Post_Media_Count",
    "Responsetype",
    "Price",
    "Post_ID",
    "Media_ID",
    "Text",
)
ROWS = []
app = None


def process_download_cart():
    while True:
        global app
        while app and not app.row_queue.empty():
            if process_download_cart.counter == 0:
                if not network.check_cdm():
                    log.info(
                        "error was raised by cdm checker\ncdm will not be check again\n\n"
                    )
                else:
                    log.info("cdm checker was fine\ncdm will not be check again\n\n")
                # should be done once before downloads
                log.info("Getting Models")

            process_download_cart.counter = process_download_cart.counter + 1
            log.info("Getting items from queue")
            try:
                row, key = app.row_queue.get()
                restype = app.row_names.index("Responsetype")
                username = app.row_names.index("UserName")
                post_id = app.row_names.index("Post_ID")
                media_id = app.row_names.index("Media_ID")
                url = None
                if row[restype].plain == "message":
                    url = constants.getattr("messageTableSPECIFIC").format(
                        row[username].plain, row[post_id].plain
                    )
                elif row[restype].plain == "post":
                    url = f"{row[post_id]}"
                elif row[restype].plain == "highlights":
                    url = constants.getattr("storyEP").format(row[post_id].plain)
                elif row[restype].plain == "stories":
                    url = constants.getattr("highlightsWithAStoryEP").format(
                        row[post_id].plain
                    )
                else:
                    log.info("URL not supported")
                    continue
                log.info(f"Added url {url}")
                log.info("Sending URLs to OF-Scraper")
                media_dict = manual.get_media_from_urls(urls=[url])
                # None for stories and highlights
                matchID = int(row[media_id].plain)
                medialist = list(
                    filter(
                        lambda x: x.id == matchID if x.id else None,
                        list(media_dict.values())[0],
                    )
                )
                media = medialist[0] if len(medialist) > 0 else None
                model_id = media.post.model_id
                username = media.post.username
                args = read_args.retriveArgs()
                args.username = set([username])
                write_args.setArgs(args)
                selector.all_subs_helper()
                log.info(
                    f"Downloading individual media for {username} {media.filename}"
                )
                operations.create_tables(model_id=model_id, username=username)
                operations.create_backup(model_id, username)
                operations.write_profile_table(model_id=model_id, username=username)
                values = downloadnormal.process_dicts(
                    username,
                    model_id,
                    [media],
                )
                if values == None or values[-1] == 1:
                    raise Exception("Download is marked as skipped")
                log.info("Download Finished")
                app.update_cell(key, "Download_Cart", "[downloaded]")
                app.update_cell(key, "Downloaded", True)

            except Exception as E:
                app.update_downloadcart_cell(key, "[failed]")
                log.debug(E)
        time.sleep(10)


def post_checker():
    user_dict = {}

    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        links = list(url_helper())
        for ele in links:
            name_match = re.search(
                f"onlyfans.com/({constants.getattr('USERNAME_REGEX')}+$)", ele
            )
            name_match2 = re.search(f"^{constants.getattr('USERNAME_REGEX')}+$", ele)

            if name_match:
                user_name = name_match.group(1)
                log.info(f"Getting Full Timeline for {user_name}")
                model_id = profile.get_id(user_name)
            elif name_match2:
                user_name = name_match2.group(0)
                model_id = profile.get_id(user_name)
            else:
                continue
            if user_dict.get(user_name):
                continue

            oldtimeline = cache.get(f"timeline_check_{model_id}", default=[])
            user_dict[user_name] = {}
            user_dict[user_name] = user_dict[user_name] or []
            if len(oldtimeline) > 0 and not read_args.retriveArgs().force:
                user_dict[user_name].extend(oldtimeline)
            else:
                user_dict[user_name] = {}
                user_dict[user_name] = user_dict[user_name] or []
                data = timeline.get_timeline_media(model_id, user_name, forced_after=0)
                user_dict[user_name].extend(data)
                cache.set(
                    f"timeline_check_{model_id}",
                    data,
                    expire=constants.getattr("DAY_SECONDS"),
                )
                cache.close()

            oldarchive = cache.get(f"archived_check_{model_id}", default=[])
            if len(oldarchive) > 0 and not read_args.retriveArgs().force:
                user_dict[user_name].extend(oldarchive)
            else:
                data = archive.get_archived_media(model_id, user_name, forced_after=0)
                user_dict[user_name].extend(data)
                cache.set(
                    f"archived_check_{model_id}",
                    data,
                    expire=constants.getattr("DAY_SECONDS"),
                )
                cache.close()

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
                post_id = num_match.group(1)
                model_id = profile.get_id(user_name)
                log.info(f"Getting Invidiual Link for {user_name}")
                if not user_dict.get(user_name):
                    user_dict[name_match.group(1)] = {}
                data = timeline.get_individual_post(post_id, c)
                user_dict[user_name] = user_dict[user_name] or []
                user_dict[user_name].append(data)

    ROWS = []
    for user_name in user_dict.keys():
        downloaded = get_downloaded(user_name, model_id, True)
        media = get_all_found_media(user_name, user_dict[user_name])
        ROWS.extend(row_gather(media, downloaded, user_name))
    reset_url()
    set_count(ROWS)
    network.check_cdm()
    thread_starters(ROWS)


def reset_url():
    # clean up args once check modes are ready to launch
    args = read_args.retriveArgs()
    argdict = vars(args)
    if argdict.get("url"):
        read_args.retriveArgs().url = None
    if argdict.get("file"):
        read_args.retriveArgs().file = None
    if argdict.get("username"):
        read_args.retriveArgs().username = None
    write_args.setArgs(args)


def set_count(ROWS):
    for count, ele in enumerate(ROWS):
        ele[0] = count + 1


def message_checker():
    links = list(url_helper())
    ROWS = []
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
        else:
            continue
        log.info(f"Getting Messages/Paid content for {user_name}")
        # messages
        messages = None
        oldmessages = cache.get(f"message_check_{model_id}", default=[])
        log.debug(f"Number of messages in cache {len(oldmessages)}")

        if len(oldmessages) > 0 and not read_args.retriveArgs().force:
            messages = oldmessages
        else:
            messages = messages_.get_messages(model_id, user_name, forced_after=0)
            cache.set(
                f"message_check_{model_id}",
                messages,
                expire=constants.getattr("DAY_SECONDS"),
            )
        oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
        paid = None
        # paid content
        if len(oldpaid) > 0 and not read_args.retriveArgs().force:
            paid = oldpaid
        else:
            paid = paid_.get_paid_posts(user_name, model_id)
            cache.set(
                f"purchased_check_{model_id}",
                paid,
                expire=constants.getattr("DAY_SECONDS"),
            )
        media = get_all_found_media(user_name, messages + paid)
        unduped = []
        id_set = set()
        for ele in media:
            if ele.id == None or ele.id not in id_set:
                unduped.append(ele)
                id_set.add(ele.id)
        downloaded = get_downloaded(user_name, model_id, True)

        ROWS.extend(row_gather(unduped, downloaded, user_name))

    reset_url()
    set_count(ROWS)
    network.check_cdm()
    thread_starters(ROWS)


def purchase_checker():
    user_dict = {}
    auth.make_headers(auth.read_auth())
    ROWS = []
    for user_name in read_args.retriveArgs().username:
        user_name = profile.scrape_profile(user_name)["username"]
        user_dict[user_name] = user_dict.get(user_name, [])
        model_id = profile.get_id(user_name)
        oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
        paid = None

        if len(oldpaid) > 0 and not read_args.retriveArgs().force:
            paid = oldpaid
        else:
            paid = paid_.get_paid_posts(user_name, model_id)
            cache.set(
                f"purchased_check_{model_id}",
                paid,
                expire=constants.getattr("DAY_SECONDS"),
            )
        downloaded = get_downloaded(user_name, model_id)
        media = get_all_found_media(user_name, paid)
        ROWS.extend(row_gather(media, downloaded, user_name))
    reset_url()
    set_count(ROWS)
    network.check_cdm()
    thread_starters(ROWS)


def stories_checker():
    user_dict = {}
    ROWS = []
    for user_name in read_args.retriveArgs().username:
        user_name = profile.scrape_profile(user_name)["username"]
        user_dict[user_name] = user_dict.get(user_name, [])
        model_id = profile.get_id(user_name)
        stories = highlights.get_stories_post(model_id)
        highlights_ = highlights.get_highlight_post(model_id)
        highlights_ = list(
            map(
                lambda x: posts_.Post(x, model_id, user_name, "highlights"), highlights_
            )
        )
        stories = list(
            map(lambda x: posts_.Post(x, model_id, user_name, "stories"), stories)
        )

        downloaded = get_downloaded(user_name, model_id)
        media = []
        [media.extend(ele.all_media) for ele in stories + highlights_]
        ROWS.extend(row_gather(media, downloaded, user_name))
    reset_url()
    set_count(ROWS)
    network.check_cdm()
    thread_starters(ROWS)


def url_helper():
    out = []
    out.extend(read_args.retriveArgs().file or [])
    out.extend(read_args.retriveArgs().url or [])
    return map(lambda x: x.strip(), out)


def get_all_found_media(user_name, posts):
    temp = []
    model_id = profile.get_id(user_name)
    posts_array = list(map(lambda x: posts_.Post(x, model_id, user_name), posts))
    [temp.extend(ele.all_media) for ele in posts_array]
    return temp


def get_downloaded(user_name, model_id, paid=False):
    downloaded = {}
    operations.create_tables(model_id=model_id, username=user_name)
    operations.create_backup(model_id, user_name)

    paid = get_paid_ids(model_id, user_name) if paid else []
    [
        downloaded.update({ele: downloaded.get(ele, 0) + 1})
        for ele in operations.get_media_ids_downloaded(
            model_id=model_id, username=user_name
        )
        + paid
    ]

    return downloaded


def get_paid_ids(model_id, user_name):
    oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
    paid = None

    if len(oldpaid) > 0 and not read_args.retriveArgs().force:
        paid = oldpaid
    else:
        paid = paid_.get_paid_posts(user_name, model_id)
        cache.set(
            f"purchased_check_{model_id}", paid, expire=constants.getattr("DAY_SECONDS")
        )
    media = get_all_found_media(user_name, paid)
    media = list(filter(lambda x: x.canview == True, media))
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
    app = table.InputApp()
    app.mutex = threading.Lock()
    app.row_queue = queue.Queue()
    ROWS = get_first_row()
    ROWS.extend(ROWS_)

    app.table_data = ROWS
    app.row_names = ROW_NAMES
    app._filtered_rows = app.table_data[1:]
    app.run()


def get_first_row():
    return [ROW_NAMES]


def texthelper(text):
    text = text or ""
    text = textwrap.dedent(text)
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


def row_gather(media, downloaded, username):
    # fix text

    mediadict = {}
    [
        mediadict.update({ele.id: mediadict.get(ele.id, []) + [ele]})
        for ele in list(filter(lambda x: x.canview, media))
    ]
    out = []
    media = sorted(media, key=lambda x: arrow.get(x.date), reverse=True)
    for count, ele in enumerate(media):
        out.append(
            [
                None,
                checkmarkhelper(ele),
                username,
                ele.id in downloaded
                or cache.get(ele.postid) != None
                or cache.get(ele.filename) != None,
                unlocked_helper(ele),
                times_helper(ele, mediadict, downloaded),
                ele.numeric_length,
                ele.mediatype,
                datehelper(ele.formatted_postdate),
                len(ele._post.post_media),
                ele.responsetype,
                "Free" if ele._post.price == 0 else "{:.2f}".format(ele._post.price),
                ele.postid,
                ele.id,
                texthelper(ele.text),
            ]
        )
    return out
