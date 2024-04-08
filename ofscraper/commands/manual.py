import logging
import traceback
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
import ofscraper.utils.args.user as user_helper
from ofscraper.utils.context.run_async import run


def manual_download(urls=None):
    log = logging.getLogger("shared")
    try:
        network.check_cdm()
        allow_manual_dupes()
        url_dicts = process_urls(urls)
        all_media=[item for media_list in url_dicts.values() for item in media_list.get("media_list", [])]
        all_posts=[item for post_list in url_dicts.values() for item in post_list.get("post_list", [])]
        log.debug(f"Number of values from media dict  {len(all_media)}")
        log.debug(f"Number of values from post dict  {len(all_posts)}")
        if len(all_media)==0 and len(all_posts)==0:
            return
        set_user_data(url_dicts)
        for _,value in url_dicts.items():
            model_id = value.get("model_id")
            username = value.get("username")
            model_id = value.get("model_id")
            username = value.get("username")
            log.info(f"Downloading individual media for {username}")
            operations.table_init_create(model_id=model_id, username=username)
            operations.make_changes_to_content_tables(value.get("post_list",[]),model_id=model_id,username=username)
            download.download_process(username, model_id, value.get("media_list",[]), posts=None)
            operations.batch_mediainsert(value.get("media_list"),username=username,model_id=model_id)
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        raise e


def allow_manual_dupes():
    args = read_args.retriveArgs()
    args.force_all = True
    write_args.setArgs(args)


def set_user_data(url_dicts):
    user_helper.set_users_arg([nested_dict.get("username") for nested_dict in url_dicts.values()])
    selector.all_subs_helper()

def process_urls(urls):
    out_dict={}

    for url in url_helper(urls):
        response = get_info(url)
        model = response[0]
        postid = response[1]
        type = response[2]
        if type == "post":  
            user_data=profile.scrape_profile(model)
            model_id = user_data.get("id")
            username= user_data.get("username")
            out_dict.setdefault(model_id, {})["model_id"]= model_id
            out_dict.setdefault(model_id, {})["username"]= username

            value = timeline.get_individual_post(postid)

            out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(get_all_media(postid, model_id, value))
            out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(get_post_item(model_id, value))
        elif type == "msg":
            user_data=profile.scrape_profile(model)
            model_id = user_data.get("id")
            username= user_data.get("username")
            out_dict.setdefault(model_id, {})["model_id"]= model_id
            out_dict.setdefault(model_id, {})["username"]= username
            
            value = messages_.get_individual_post(model_id, postid)
            out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(get_all_media(postid, model_id, value))
            out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(get_post_item(model_id, value))
        elif type == "msg2":
            user_data=profile.scrape_profile(model)
            username= user_data.get("username")
            model_id=user_data.get("id")
            out_dict.setdefault(model_id, {})["model_id"]= model_id
            out_dict.setdefault(model_id, {})["username"]= username

            value = messages_.get_individual_post(model_id, postid)
            out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(get_all_media(postid, model_id, value))
            out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(get_post_item(model_id, value))
        elif type == "unknown":
            value = unknown_type_helper(postid) or {}
            model_id = value.get("author", {}).get("id")
            if not model_id:
                continue
            username=profile.scrape_profile(model_id).get("username")
            out_dict.setdefault(model_id, {})["model_id"]= model_id
            out_dict.setdefault(model_id, {})["username"]= username

            out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(get_all_media(postid, model_id, value))
            out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(get_post_item(model_id, value))
        elif type == "highlights":
            value = highlights_.get_individual_highlights(postid) or {}
            model_id = value.get("userId")
            if not model_id:
                continue
            username= profile.scrape_profile(model_id).get("username")
            out_dict.setdefault(model_id, {})["model_id"]= model_id
            out_dict.setdefault(model_id, {})["username"]= username

            out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(get_all_media(postid, model_id, value,responsetype="highlights"))
            out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(get_post_item(model_id, value,responsetype="highlights"))
            # special case
        elif type == "stories":
            value = highlights_.get_individual_stories(postid) or {}
            model_id = value.get("userId")
            if not model_id:
                continue
            username= profile.scrape_profile(model_id).get("username")
            out_dict.setdefault(model_id, {})["model_id"]= model_id
            out_dict.setdefault(model_id, {})["username"]= username
            out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(get_all_media(postid, model_id, value,responsetype="stories"))
            out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(get_post_item(model_id, value,responsetype="stories"))
            # special case
    return out_dict


def unknown_type_helper(postid):
    return timeline.get_individual_post(postid)


def get_post_item(model_id, value, responsetype=None):
    if value == None:
        return []
    user_name = profile.scrape_profile(model_id)["username"]
    post = posts_.Post(value, model_id, user_name, responsetype=responsetype)
    return [post]


def get_all_media(posts_id, model_id, value,responsetype=None):
    value = value or {}
    media = []
    if model_id == None:
        return {}
    user_name = profile.scrape_profile(model_id)["username"]
    post_item = posts_.Post(value, model_id, user_name, responsetype=responsetype)
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
    return media

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
    out = []
    out.extend(args.get("file", []) or [])
    out.extend(args.get("url", []) or [])
    out.extend(urls or [])
    return map(lambda x: x.strip(), out)
