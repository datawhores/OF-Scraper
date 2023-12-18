import logging
import re

import ofscraper.api.highlights as highlights_
import ofscraper.api.messages as messages_
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.constants as constants
import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.utils.args as args_
import ofscraper.utils.network as network
import ofscraper.utils.of as of


def manual_download(urls=None):
    log = logging.getLogger("shared")
    network.check_cdm()
    media_dict = get_media_from_urls(urls)
    log.debug(f"Media dict length {len(list(media_dict.values()))}")
    args = args_.getargs()
    args.dupe = True
    args_.changeargs(args)

    for value in media_dict.values():
        if len(value) == 0:
            continue
        model_id = value[0].post.model_id
        username = value[0].post.username
        log.info(f"Downloading individual media for {username}")
        operations.create_tables(model_id=model_id, username=username)
        operations.create_backup(model_id, username)
        operations.write_profile_table(model_id=model_id, username=username)
        download.download_picker(username, model_id, value)

    log.info(f"Finished")


def get_media_from_urls(urls):
    args = args_.getargs()
    args.dupe = True
    args_.changeargs(args)
    user_name_dict = {}
    id_dict = {}
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        for url in url_helper(urls):
            response = get_info(url)
            model = response[0]
            postid = response[1]
            type = response[2]
            if type == "post":
                model_id = user_name_dict.get(model) or profile.get_id(model)
                user_name_dict[model] = model_id
                id_dict[model_id] = id_dict.get(model_id, []) + [
                    timeline.get_individual_post(postid, c=c)
                ]
            elif type == "msg":
                model_id = model
                id_dict[model_id] = id_dict.get(model_id, []) + [
                    messages_.get_individual_post(model_id, postid, c=c)
                ]
            elif type == "msg2":
                model_id = user_name_dict.get(model) or profile.get_id(model)
                id_dict[model_id] = id_dict.get(model_id, []) + [
                    messages_.get_individual_post(model_id, postid, c=c)
                ]
            elif type == "unknown":
                data = unknown_type_helper(postid, c) or {}
                model_id = data.get("author", {}).get("id")
                id_dict[model_id] = id_dict.get(model_id, []) + [data]
            elif type == "highlights":
                data = highlights_.get_individual_highlights(postid, c) or {}
                model_id = data.get("userId")
                id_dict[model_id] = id_dict.get(model_id, []) + [data]
                # special case
                return get_all_media(id_dict, "highlights")
            elif type == "stories":
                data = highlights_.get_individual_stories(postid, c) or {}
                model_id = data.get("userId")
                id_dict[model_id] = id_dict.get(model_id, []) + [data]
                # special case
                return get_all_media(id_dict, "stories")

            else:
                continue

    return get_all_media(id_dict)


def unknown_type_helper(postid, client):
    # try to get post by id
    return timeline.get_individual_post(postid, client)


def get_all_media(id_dict, inputtype=None):
    media_dict = {}

    for model_id, value in id_dict.items():
        if model_id == None:
            continue
        temp = []
        user_name = profile.scrape_profile(model_id)["username"]
        posts_array = list(
            map(
                lambda x: posts_.Post(x, model_id, user_name, responsetype=inputtype),
                value,
            )
        )
        [temp.extend(ele.media) for ele in posts_array]
        if len(temp) == 0:
            temp.extend(paid_failback(model_id, user_name))
        media_dict[model_id] = temp
    return media_dict


def paid_failback(id, username):
    logging.getLogger("shared").debug(
        "Using failback search because query return 0 media"
    )
    return of.process_paid_post(id, username)


def get_info(url):
    search1 = re.search(
        f"chats/chat/({constants.NUMBER_REGEX}+)/.*?({constants.NUMBER_REGEX}+)", url
    )
    search2 = re.search(f"/({constants.NUMBER_REGEX}+)/stories/highlights", url)
    search3 = re.search(f"/stories/highlights/({constants.NUMBER_REGEX}+)", url)

    search4 = re.search(f"/({constants.NUMBER_REGEX}+)/stories", url)
    search5 = re.search(
        f"chats/({constants.USERNAME_REGEX}+)/.*?(id|firstId)=({constants.NUMBER_REGEX}+)",
        url,
    )
    search6 = re.search(
        f"/({constants.NUMBER_REGEX}+)/({constants.USERNAME_REGEX}+)", url
    )
    search7 = re.search(f"^{constants.NUMBER_REGEX}+$", url)
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
    args = args_.getargs()
    args = vars(args)
    out = []
    out.extend(args.get("file", []) or [])
    out.extend(args.get("url", []) or [])
    out.extend(urls or [])
    return map(lambda x: x.strip(), out)
