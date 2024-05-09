"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import logging
import traceback

import arrow

import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.filters.media.main as filters
import ofscraper.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.constants as constants
from ofscraper.__version__ import __version__
from ofscraper.commands.actions.download.post import process_areas_helper
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)
from ofscraper.commands.actions.scrape_context import scrape_context_manager
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.api.init as init


log = logging.getLogger("shared")

def force_add_arguments():
    args = read_args.retriveArgs()
    args.action = "download"
    write_args.setArgs(args)


def metadata_stray_media(username,model_id, media):
    all_media = []
    curr_media_set = set(map(lambda x: str(x.id), media))
    args = read_args.retriveArgs()
    if "Timeline" in args.download_area:
        all_media.extend(get_timeline_media(model_id=model_id, username=username))
    if "Messages" in args.download_area:
        all_media.extend(get_messages_media(model_id=model_id, username=username))
    if "Archived" in args.download_area:
        all_media.extend(get_archived_media(model_id=model_id, username=username))
    if not bool(all_media):
        return
    filtered_media = list(
        filter(
            lambda x: str(x["media_id"]) not in curr_media_set
            and arrow.get(x.get("posted_at") or 0).is_between(args.after, args.before)
            and x.get("downloaded") != 1,
            all_media,
        )
    )
    log.info(f"Found {len(filtered_media)} stray items to mark as downloaded")
    batch_set_media_downloaded(filtered_media, model_id=model_id, username=username)


def metadata_normal():
    metadata_action = read_args.retriveArgs().metadata
    mark_stray = read_args.retriveArgs().mark_stray
    with scrape_context_manager():
        profile_tools.print_current_profile()
        init.print_sign_status()
        userdata = userselector.getselected_usernames(rescan=False)
        length = len(userdata)

        for count, ele in enumerate(userdata):
            log.warning(f"Metadata action progressing on model {count+1}/{length} models ")
            if constants.getattr("SHOW_AVATAR") and ele.avatar:
                log.warning(f"Avatar : {ele.avatar}")

            log.warning(
                f"""
                    Perform Meta {metadata_action} with 
                    Mark Stray: {mark_stray}
                    for [bold]{ele.name}[/bold]\n[bold]
                    Subscription Active:[/bold] {ele.active}"""
            )
            try:
                model_id = ele.id
                username = ele.name

                media, _ = process_areas_helper(ele, model_id)
                operations.table_init_create(model_id=model_id, username=username)
                filterMedia = filters.filterMedia(media)
                download.download_process(username, model_id, filterMedia)
                metadata_stray_media(username,model_id, media)
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())

def metadata_user_first():
    with scrape_context_manager():
        profile_tools.print_current_profile()
        init.print_sign_status()
        data = {}
        for user in userselector.getselected_usernames(rescan=False):
            data.update(process_user_first_data_retriver(user))
        count=0
        length=(len(data.keys()))
        for model_id, val in data.items():
            username = val["username"]
            media=val['media']
            avatar=val['avatar']
            try:
                log.warning(
                f"Download action progressing on model {count+1}/{length} models "
                )
                if constants.getattr("SHOW_AVATAR") and avatar:
                    log.warning(f"Avatar : {avatar}")
                filterMedia = filters.filterMedia(media)
                download.download_process(
                    username, model_id, filterMedia
                )
                metadata_stray_media(username,model_id, media)
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())
            
            finally:
                count=count+1

def process_user_first_data_retriver(ele):
    model_id = ele.id
    username = ele.name
    avatar=ele.avatar
    metadata_action = read_args.retriveArgs().metadata
    mark_stray = read_args.retriveArgs().mark_stray
    if constants.getattr("SHOW_AVATAR") and avatar:
        log.warning(f"Avatar : {avatar}")
    log.warning(
        f"""
            Perform Meta {metadata_action} with 
            Mark Stray: {mark_stray}
            for [bold]{ele.name}[/bold]\n[bold]
            Subscription Active:[/bold] {ele.active}"""
    )
    try:
        model_id = ele.id
        username = ele.name
        operations.table_init_create(model_id=model_id, username=username)
        media, _ = process_areas_helper(ele, model_id)
        return {model_id: {"username": username, "media": media,"avatar":avatar}}
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())
def metadata():
    if not read_args.retriveArgs().users_first:
        metadata_normal()
    else:
        metadata_user_first()


def process_selected_areas():
    log.debug("[bold blue] Running Metadata Mode [/bold blue]")
    force_add_arguments()
    actions.select_areas()
    metadata()
