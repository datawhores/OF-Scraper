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

import copy
import logging
import traceback

import arrow

import ofscraper.api.init as init
import ofscraper.api.profile as profile
import ofscraper.classes.models as models
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.filters.media.main as filters
import ofscraper.models.selector as userselector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.__version__ import __version__
from ofscraper.commands.helpers.context import (
    get_user_action_function,
    get_userfirst_action_execution_function,
    get_userfirst_data_function,
)
from ofscraper.commands.helpers.shared import run_action_bool
from ofscraper.commands.helpers.strings import avatar_str, metadata_str
from ofscraper.commands.scraper.post import process_all_paid, process_areas_helper
from ofscraper.commands.scraper.scrape_context import scrape_context_manager
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


def metadata():
    with progress_utils.setup_activity_progress_live(stop=True):
        if read_args.retriveArgs().scrape_paid:
            metadata_paid_all()
        if not run_action_bool():
            return
        userdata, session = prepare()
        if not read_args.retriveArgs().users_first:
            process_users_metadata_normal(userdata, session)
        else:
            metadata_user_first(userdata, session)


@run
async def process_users_metadata_normal(userdata, session):
    user_action_funct = get_user_action_function(process_metadata_for_user)
    progress_utils.update_activity_count(description="Users with Updated Metadata")
    async with session:
        for ele in userdata:
            await user_action_funct(user=ele, session=session)


@run
async def metadata_user_first(userdata, session):
    data = await get_userfirst_data_function(metadata_data_user_first)(
        userdata, session
    )

    await get_userfirst_action_execution_function(execute_metadata_action_user_first)(
        data
    )


def metadata_paid_all(user_dict=None):
    progress_utils.update_activity_task("Scraping Entire Paid page")
    old_args = copy.deepcopy(read_args.retriveArgs())
    force_change_metadata()
    user_dict = process_all_paid()
    oldUsers = userselector.get_ALL_SUBS_DICT()
    length = len(list(user_dict.keys()))
    for count, value in enumerate(user_dict.values()):
        model_id = value["model_id"]
        username = value["username"]
        posts = value["posts"]
        medias = value["medias"]
        avatar = value["avatar"]
        if constants.getattr("SHOW_AVATAR") and avatar:
            logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
        log.warning(
            f"Download paid content for {model_id}_{username} number:{count+1}/{length} models "
        )
        userselector.set_ALL_SUBS_DICTVManger(
            {username: models.Model(profile.scrape_profile(model_id))}
        )
        download.download_process(username, model_id, medias, posts=posts)
    # restore settings
    userselector.set_ALL_SUBS_DICT(oldUsers)
    write_args.setArgs(old_args)


def metadata_stray_media(username, model_id, media):
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
            and arrow.get(x.get("posted_at") or 0).is_between(
                arrow.get(args.after or 0), args.before
            )
            and x.get("downloaded") != 1
            and x.get("unlocked") != 0,
            all_media,
        )
    )
    log.info(f"Found {len(filtered_media)} stray items to mark as locked")
    batch_set_media_downloaded(filtered_media, model_id=model_id, username=username)


async def process_metadata_for_user(user=None, session=None):
    try:

        model_id = user.id
        all_media, _, _ = await process_areas_helper(user, model_id, c=session)
        await get_user_action_execution_function(execute_metadata_action_on_user)(
            user=user, media=all_media
        )
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())


async def execute_metadata_action_on_user(user=None, media=None):
    username = user.name

    model_id = user.id
    operations.table_init_create(model_id=model_id, username=username)
    filterMedia = filters.filterMedia(media, username=username, model_id=model_id)
    progress_utils.update_activity_task(
        description=metadata_str.format(username=username)
    )
    await download.download_process(username, model_id, filterMedia)
    metadata_stray_media(username, model_id, media)


async def execute_metadata_action_user_first(data):
    progress_utils.update_activity_task(
        description="Performing Metadata Actions on Users"
    )
    progress_utils.update_user_activity(
        description="Users with Metadata updated", completed=0
    )
    for model_id, val in data.items():
        username = val["username"]
        media = val["media"]
        ele = val["ele"]
        progress_utils.update_activity_task(
            description=metadata_str.format(username=username)
        )
        try:

            await get_user_action_execution_function(execute_metadata_action_on_user)(
                media=media, user=ele
            )
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            log.traceback_(f"failed with exception: {e}")
            log.traceback_(traceback.format_exc())


@run
async def metadata_data_user_first(session, ele):
    try:
        return await process_ele_user_first_data_retriver(ele=ele, session=session)
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())


async def process_ele_user_first_data_retriver(ele=None, session=None):
    data = {}
    progress_utils.switch_api_progress()
    model_id = ele.id
    username = ele.name
    avatar = ele.avatar
    active = ele.active
    metadata_action = read_args.retriveArgs().metadata
    mark_stray = read_args.retriveArgs().mark_stray
    log.warning(
        f"""
    Perform Meta {metadata_action} with
    Mark Stray: {mark_stray}
    for [bold]{username}[/bold]\n[bold]
    Subscription Active:[/bold] {active}
    """
    )
    try:
        model_id = ele.id
        username = ele.name
        await operations.table_init_create(model_id=model_id, username=username)
        media, _, _ = await process_areas_helper(ele, model_id, c=session)
        return {
            model_id: {
                "username": username,
                "media": media,
                "avatar": avatar,
                "ele": ele,
            }
        }
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())
    return data


def process_selected_areas():
    log.debug("[bold blue] Running Metadata Mode [/bold blue]")
    force_change_download()
    with scrape_context_manager():
        with progress_utils.setup_activity_progress_live(stop=True):
            if read_args.retriveArgs().metadata:
                metadata()


def prepare():
    profile_tools.print_current_profile()
    init.print_sign_status()
    userdata = userselector.getselected_usernames(rescan=False)
    session = sessionManager.sessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        retries=constants.getattr("API_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )
    return userdata, session


def force_change_download():
    args = read_args.retriveArgs()
    args.action = "download"
    write_args.setArgs(args)


def force_change_metadata():
    args = read_args.retriveArgs()
    args.metadata = args.scrape_paid
    write_args.setArgs(args)
