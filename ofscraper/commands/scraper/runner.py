import logging

import ofscraper.api.init as init
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.commands.scraper.actions.like as like_action
import ofscraper.db.operations as operations
import ofscraper.models.selector as userselector
import ofscraper.utils.actions as actions
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.commands.helpers.normal import (
    get_user_action_function,

)

from ofscraper.commands.helpers.user_first import (
    get_userfirst_action_execution_function,
    get_userfirst_data_function,
)

from ofscraper.commands.helpers.shared import run_action_bool

from ofscraper.commands.helpers.final_log import final_log
from ofscraper.commands.scraper.post import post_media_process
from ofscraper.commands.scraper.scrape_context import scrape_context_manager
from ofscraper.utils.checkers import check_auth
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@exit.exit_wrapper
def runner():
    check_auth()
    progress_utils.update_activity_task(description="Running Action Mode")
    with scrape_context_manager(
    ):
        normal_data=[]
        user_first_data=[
        ]
        scrape_paid_data=[]
        with progress_utils.setup_activity_group_live(setup=True,revert=False):
            if read_args.retriveArgs().scrape_paid:
                scrape_paid_data=download_action.scrape_paid_all()

            if not run_action_bool():
                pass

            elif read_args.retriveArgs().users_first:
                userdata, session = prepare()
                user_first_data=process_users_actions_user_first(userdata, session)
            else:
                userdata, session = prepare()
                normal_data=process_users_actions_normal(userdata, session)
        final_log(normal_data+scrape_paid_data+user_first_data)
def prepare():
    session = sessionManager.sessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        retries=constants.getattr("API_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )

    download_action.unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    actions.select_areas()

    userdata = userselector.getselected_usernames(rescan=False)
    return userdata, session


@exit.exit_wrapper
@run
async def process_users_actions_normal(userdata=None, session=None):
    progress_utils.update_user_activity(description="Users with Actions Completed")
    return await get_user_action_function( execute_user_action)(userdata,session)



async def execute_user_action( posts=None, like_posts=None,ele=None,media=None):
    actions = read_args.retriveArgs().action
    username = ele.name
    model_id = ele.id
    out=[]
    for action in actions:
        if action == "download":
            out.append(await download_action.downloader(
                ele=ele,
                posts=posts,
                media=media,
                model_id=model_id,
                username=username,
            ))
        elif action == "like":
            out.append(like_action.process_like(
                ele=ele,
                posts=like_posts,
                media=media,
                model_id=model_id,
                username=username,
            ))
        elif action == "unlike":
            out.append(like_action.process_unlike(
                ele=ele,
                posts=like_posts,
                media=media,
                model_id=model_id,
                username=username,
            ))
        return out


@exit.exit_wrapper
@run
async def process_users_actions_user_first(userdata, session):
    data = await get_userfirst_data_function(get_users_data_user_first)(
        userdata, session
    )
    progress_utils.update_activity_task(description="Performing Actions on Users")
    progress_utils.update_user_activity(
        description="Users with Actions completed", completed=0
    )

    return await get_userfirst_action_execution_function(execute_user_action)(
        data
    )


async def get_users_data_user_first(session, ele):
    return await process_ele_user_first_data_retriver(ele, session)

async def process_ele_user_first_data_retriver(ele, session):
    model_id = ele.id
    username = ele.name
    avatar = ele.avatar
    await operations.table_init_create(model_id=model_id, username=username)
    media, posts, like_posts = await post_media_process(ele, session)
    return {
        model_id: {
            "username": username,
            "posts": posts,
            "media": media,
            "avatar": avatar,
            "like_posts": like_posts,
            "ele": ele,
        }
    }
