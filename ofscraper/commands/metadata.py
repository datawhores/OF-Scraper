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
from ofscraper.commands.helpers.normal import (
    get_user_action_function_meta,
)
from ofscraper.commands.helpers.user_first import (
    get_userfirst_action_execution_function,
    get_userfirst_data_function,
)
from ofscraper.commands.helpers.shared import run_metadata_bool
from ofscraper.commands.helpers.strings import metadata_activity_str,mark_stray_str,all_paid_metadata_str,all_paid_progress_metadata_str

from ofscraper.commands.scraper.post import process_areas
from ofscraper.commands.scraper.scrape_context import scrape_context_manager
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)
from ofscraper.utils.context.run_async import run
from ofscraper.commands.helpers.final_log import final_log
from ofscraper.commands.helpers.scrape_paid import process_scrape_paid,process_user_info_printer,process_user
log = logging.getLogger("shared")


def metadata():
    with progress_utils.setup_activity_progress_live(revert=True):
        scrape_paid_data=[]
        userfirst_data=[]
        normal_data=[]
        if read_args.retriveArgs().scrape_paid:
            scrape_paid_data=metadata_paid_all()
        if not run_metadata_bool():
            pass
        
        elif not read_args.retriveArgs().users_first:
            userdata, session = prepare()
            normal_data=process_users_metadata_normal(userdata, session)
        else:
            userdata, session = prepare()
            userfirst_data=metadata_user_first(userdata, session)
    final_log(normal_data+scrape_paid_data+userfirst_data)


@run
async def process_users_metadata_normal(userdata, session):
    user_action_funct = get_user_action_function_meta(execute_metadata_action_on_user)
    progress_utils.update_user_activity(description="Users with Updated Metadata")
    return await user_action_funct(userdata, session)


@run
async def metadata_user_first(userdata, session):
    data = await get_userfirst_data_function(metadata_data_user_first)(
        userdata, session
    )
    progress_utils.update_activity_task(description="Changing Metadata for Users")
    progress_utils.update_user_activity(
        description="Users with Metadata Changed", completed=0
    )

    return await get_userfirst_action_execution_function( execute_metadata_action_on_user)(
        data
    )

@run
async def metadata_paid_all():
    old_args = copy.deepcopy(read_args.retriveArgs())
    force_change_metadata()
    out=["[bold yellow]Scrape Paid Results[/bold yellow]"]

    async for count,value,length in process_scrape_paid():
        process_user_info_printer(value,length,count,all_paid_update=all_paid_metadata_str,all_paid_activity=metadata_activity_str,
        log_progress=all_paid_progress_metadata_str

                                  
                                  )
        out.append(await process_user(value,length))
    write_args.setArgs(old_args)
    return out



def metadata_stray_media(username, model_id, media):
    all_media = []
    curr_media_set = set(map(lambda x: str(x.id), media))
    args = read_args.retriveArgs()
    progress_utils.update_activity_task(description=mark_stray_str.format(username=username))
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


async def execute_metadata_action_on_user(*args,ele=None, media=None,**kwargs):
    username = ele.name

    model_id = ele.id
    await operations.table_init_create(model_id=model_id, username=username)
    progress_utils.update_activity_task(
        description=metadata_activity_str.format(username=username)
    )
    data=await download.download_process(username, model_id, media)
    metadata_stray_media(username, model_id, media)
    return [data]



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
        media, _, _ = await process_areas(ele, model_id, c=session)
        return {
            model_id: {
                "username": username,
                "media": media,
                "avatar": avatar,
                "ele": ele,
                "posts":[],
                "like_posts":[]
            }
        }
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())
    return data


def process_selected_areas():
    log.debug("[bold deep_sky_blue2] Running Metadata Mode [/bold deep_sky_blue2]")
    force_change_download()
    progress_utils.update_activity_task(description="Running Metadata Mode")
    with scrape_context_manager():
        with progress_utils.setup_activity_group_live(revert=True):
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
