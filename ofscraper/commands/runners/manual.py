import logging
import re
import traceback

import ofscraper.data.api.highlights as highlights_
import ofscraper.data.api.messages as messages_
import ofscraper.data.api.paid as paid
import ofscraper.data.api.profile as profile
import ofscraper.classes.media as media_
import ofscraper.classes.posts as posts_
import  ofscraper.runner.manager as manager2
import ofscraper.db.operations as operations
import ofscraper.actions.actions.download.download as download
import ofscraper.data.models.manager as manager
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater

import ofscraper.utils.system.network as network
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.commands.utils.strings import download_manual_str, post_str_manual
from ofscraper.db.operations import make_changes_to_content_tables
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.utils.checkers import check_auth
from ofscraper.utils.context.run_async import run
from ofscraper.runner.close.final.final import final
from ofscraper.actions.actions.download.utils.text import textDownloader
import  ofscraper.runner.manager as manager



def manual_download(urls=None):
    try:
        network.check_cdm()
        allow_manual_dupes()
        log = logging.getLogger("shared")
        check_auth()
        url_dicts = process_urls(urls)

        with progress_utils.setup_activity_progress_live():
            progress_updater.update_activity_task(
                description="Getting data from retrived posts"
            )
            all_media = [
                item
                for media_list in url_dicts.values()
                for item in media_list.get("media_list", [])
            ]
            all_posts = [
                item
                for post_list in url_dicts.values()
                for item in post_list.get("post_list", [])
            ]
            log.debug(f"Number of values from media dict  {len(all_media)}")
            log.debug(f"Number of values from post dict  {len(all_posts)}")
            if len(all_media) == 0 and len(all_posts) == 0:
                return
            set_user_data(url_dicts)

        results = []
        for _, value in url_dicts.items():
            with progress_utils.setup_activity_progress_live():
                model_id = value.get("model_id")
                username = value.get("username")
                medialist = value.get("media_list")
                posts = value.get("post_list", [])
                log.info(download_manual_str.format(username=username))
                progress_updater.update_activity_task(
                    description=download_manual_str.format(username=username)
                )
                operations.table_init_create(model_id=model_id, username=username)
                make_changes_to_content_tables(
                    posts, model_id=model_id, username=username
                )
                batch_mediainsert(
                    value.get("media_list"), username=username, model_id=model_id
                )
                if read_args.retriveArgs().text_only:
                    result = textDownloader(posts, username)
                else:
                    result, _ = download.download_process(
                        username,model_id, medialist, posts=None
                    )
                results.append(result)

        final_action( results)

    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        raise e


def final_action(results):
    normal_data = ["Manual Mode Results"]
    normal_data.extend(results)
    final(
        normal_data=normal_data,
        scrape_paid_data=None,
        user_first_data=None,
    )


def allow_manual_dupes():
    args = read_args.retriveArgs()
    args.force_all = True
    write_args.setArgs(args)


def set_user_data(url_dicts):
    manager.Manager.model_manager.set_data_all_subs_dict(
        [nested_dict.get("username") for nested_dict in url_dicts.values()]
    )


def process_urls(urls):
    out_dict = {}
    with progress_utils.setup_api_split_progress_live(revert=False):
        for url in url_helper(urls):
            progress_updater.update_activity_task(
                description=post_str_manual.format(url=url)
            )
            response = get_info(url)
            model = response[0]
            postid = response[1]
            type = response[2]
            user_data = profile.scrape_profile(model)
            model_id = user_data.get("id")
            username = user_data.get("username")
            out_dict.setdefault(model_id, {})["model_id"] = model_id
            out_dict.setdefault(model_id, {})["username"] = username
            out_dict.setdefault(model_id, {})["user_data"] = user_data

            if type == "post":
                value = get_individual_timeline_post(postid)
                out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(
                    get_all_media(postid, model_id, value)
                )
                out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    get_post_item(model_id, value)
                )
            elif type == "msg":
                value = messages_.get_individual_messages_post(model_id, postid)
                out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(
                    get_all_media(postid, model_id, value)
                )
                out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    get_post_item(model_id, value)
                )
            elif type == "msg2":
                value = messages_.get_individual_messages_post(model_id, postid)
                out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(
                    get_all_media(postid, model_id, value)
                )
                out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    get_post_item(model_id, value)
                )
            elif type == "unknown":
                value = unknown_type_helper(postid) or {}
                model_id = value.get("author", {}).get("id")
                if not model_id:
                    continue
                out_dict.setdefault(model_id, {})["model_id"] = model_id
                out_dict.setdefault(model_id, {})["username"] = username

                out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(
                    get_all_media(postid, model_id, value)
                )
                out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    get_post_item(model_id, value)
                )
            elif type == "highlights":
                value = highlights_.get_individual_highlights(postid) or {}
                model_id = value.get("userId")
                if not model_id:
                    continue
                out_dict.setdefault(model_id, {})["model_id"] = model_id
                out_dict.setdefault(model_id, {})["username"] = username

                out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(
                    get_all_media(postid, model_id, value, responsetype="highlights")
                )
                out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    get_post_item(model_id, value, responsetype="highlights")
                )
                # special case
            elif type == "stories":
                value = highlights_.get_individual_stories(postid) or {}
                model_id = value.get("userId")
                if not model_id:
                    continue
                out_dict.setdefault(model_id, {})["model_id"] = model_id
                out_dict.setdefault(model_id, {})["username"] = username
                out_dict.setdefault(model_id, {}).setdefault("media_list", []).extend(
                    get_all_media(postid, model_id, value, responsetype="stories")
                )
                out_dict.setdefault(model_id, {}).setdefault("post_list", []).extend(
                    get_post_item(model_id, value, responsetype="stories")
                )
    return out_dict


def unknown_type_helper(postid):
    return get_individual_timeline_post(postid)


def get_post_item(model_id, value, responsetype=None):
    if value is None:
        return []
    user_name = profile.scrape_profile(model_id)["username"]
    post = posts_.Post(value, model_id, user_name, responsetype=responsetype)
    return [post]


def get_all_media(posts_id, model_id, value, responsetype=None):
    value = value or {}
    media = []
    if model_id is None:
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
    async with manager.Manager.aget_ofsession(
        backend="httpx",
        sem_count=constants.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        data = await paid.get_paid_posts(username, model_id, c=c) or []
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
