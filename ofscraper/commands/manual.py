import logging
import re

import ofscraper.api.highlights as highlights_
import ofscraper.api.messages as messages_
import ofscraper.api.paid as paid
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.classes.media as media_
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.system.network as network
from ofscraper.download.common.common import textDownloader
from ofscraper.utils.context.run_async import run


def manual_download(urls=None):
    log = logging.getLogger("shared")
    network.check_cdm()
    allow_manual_dupes()
    media_dict, posts_dict = get_media_from_urls(urls)
    log.debug(f"Number of values from media dict  {len(list(media_dict.values()))}")
    log.debug(f"Number of values from post dict  {len(list(posts_dict.values()))}")

    get_manual_usernames(media_dict)
    selector.all_subs_helper()
    for value in filter(lambda x: len(x) > 0, media_dict.values()):
        model_id = value[0].post.model_id
        username = value[0].post.username
        log.info(f"Downloading individual media for {username}")
        operations.table_init_create(model_id=model_id, username=username)
        download.download_process(username, model_id, value, posts=None)
    textDownloader(posts_dict.values(), username=username)


def allow_manual_dupes():
    args = read_args.retriveArgs()
    args.dupe = True
    write_args.setArgs(args)


def get_manual_usernames(media_dict):
    usernames = []
    for value in media_dict.values():
        if len(value) == 0:
            continue
        usernames.append(value[0].post.username)
    args = read_args.retriveArgs()
    args.username = set(usernames)
    write_args.setArgs(args)


def get_media_from_urls(urls):
    user_name_dict = {}
    media_dict = {}
    post_dict = {}
    for url in url_helper(urls):
        response = get_info(url)
        model = response[0]
        postid = response[1]
        type = response[2]
        if type == "post":
            model_id = user_name_dict.get(model) or profile.get_id(model)
            value = timeline.get_individual_post(postid)
            media_dict.update(get_all_media(postid, model_id, value))
            post_dict.update(get_post_item(model_id, value))
        elif type == "msg":
            model_id = model
            value = messages_.get_individual_post(model_id, postid)
            media_dict.update(get_all_media(postid, model_id, value))
            post_dict.update(get_post_item(model_id, value))
        elif type == "msg2":
            model_id = user_name_dict.get(model) or profile.get_id(model)
            value = messages_.get_individual_post(model_id, postid)
            media_dict.update(get_all_media(postid, model_id, value))
            post_dict.update(get_post_item(model_id, value))
        elif type == "unknown":
            value = unknown_type_helper(postid) or {}
            model_id = value.get("author", {}).get("id")
            media_dict.update(get_all_media(postid, model_id, value))
            post_dict.update(get_post_item(model_id, value))
        elif type == "highlights":
            value = highlights_.get_individual_highlights(postid) or {}
            model_id = value.get("userId")
            media_dict.update(get_all_media(postid, model_id, value, "highlights"))
            post_dict.update(get_post_item(model_id, value, "highlights"))
            # special case
        elif type == "stories":
            value = highlights_.get_individual_stories(postid) or {}
            model_id = value.get("userId")
            media_dict.update(get_all_media(postid, model_id, value, "stories"))
            post_dict.update(get_post_item(model_id, value, "stories"))
            # special case
    return media_dict, post_dict


def unknown_type_helper(postid):
    return timeline.get_individual_post(postid)


def get_post_item(model_id, value, inputtype=None):
    if value == None:
        return []
    user_name = profile.scrape_profile(model_id)["username"]
    post = posts_.Post(value, model_id, user_name, responsetype=inputtype)
    return {post.id: post}


def get_all_media(posts_id, model_id, value, inputtype=None):
    media_dict = {}
    value = value or {}
    media = []
    if model_id == None:
        return {}
    user_name = profile.scrape_profile(model_id)["username"]
    post_item = posts_.Post(value, model_id, user_name, responsetype=inputtype)
    media = post_item.media
    media = list(
        filter(
            lambda x: isinstance(x, media_.Media)
            and (str(x.id) == str(posts_id) or str(x.postid) == str(posts_id)),
            media,
        )
    )
    if len(media) == 0:
        media.extend(paid_failback(posts_id, model_id, user_name))
    media_dict[model_id] = media
    return media_dict


@run
async def paid_failback(post_id, model_id, username):
    logging.getLogger("shared").debug(
        "Using failback search because query return 0 media"
    )
    post_id = str(post_id)
    async with sessionbuilder.sessionBuilder(backend="httpx") as c:
        data = await paid.get_paid_posts(id, username, c=c) or []
        posts = list(
            map(lambda x: posts_.Post(x, model_id, username, responsetype="paid"), data)
        )
        output = []
        [output.extend(post.media) for post in posts]
        return list(
            filter(
                lambda x: isinstance(x, media_.Media)
                and (str(x.id) == post_id or str(x.postid) == post_id),
                output,
            )
        )


def get_info(url):
    search1 = re.search(
        f"chats/chat/({constants.getattr('NUMBER_REGEX')}+)/.*?({constants.getattr('NUMBER_REGEX')}+)",
        url,
    )
    search2 = re.search(
        f"/({constants.getattr('NUMBER_REGEX')}+)/stories/highlights", url
    )
    search3 = re.search(
        f"/stories/highlights/({constants.getattr('NUMBER_REGEX')}+)", url
    )

    search4 = re.search(f"/({constants.getattr('NUMBER_REGEX')}+)/stories", url)
    search5 = re.search(
        f"chats/({constants.getattr('USERNAME_REGEX')}+)/.*?(id|firstId)=({constants.getattr('NUMBER_REGEX')}+)",
        url,
    )
    search6 = re.search(
        f"/({constants.getattr('NUMBER_REGEX')}+)/({constants.getattr('USERNAME_REGEX')}+)",
        url,
    )
    search7 = re.search(f"^{constants.getattr('NUMBER_REGEX')}+$", url)
    # model,postid,type

    if search1:
        return search1.group(1), search1.group(2), "msg"
    elif search2 or search3:
        search = search2 or search3
        return None, search.group(1), "highlights"
    elif search4:
        return None, search4.group(1), "stories"

    elif search5:
        return search5.group(1), search5.group(3), "msg2"

    elif search6:
        return search6.group(2), search6.group(1), "post"
    elif search7:
        return None, search7.group(0), "unknown"

    return None, None, None


def url_helper(urls):
    args = read_args.retriveArgs()
    args = vars(args)
    out = []
    out.extend(args.get("file", []) or [])
    out.extend(args.get("url", []) or [])
    out.extend(urls or [])
    return map(lambda x: x.strip(), out)
