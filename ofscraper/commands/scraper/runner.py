import logging
import traceback

import ofscraper.api.init as init
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.db.operations as operations
import ofscraper.models.selector as userselector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.scraper.scrape_context import scrape_context_manager
from ofscraper.commands.scraper.post import post_media_process
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.commands.scraper.actions.like as like_action
from ofscraper.utils.context.run_async import run
from ofscraper.utils.checkers import check_auth
import ofscraper.utils.actions as actions



from ofscraper.commands.helpers.context import user_first_data_inner_context,user_first_action_runner_inner_context,get_user_action_function,get_user_action_execution_function,get_userfirst_data_function,get_userfirst_action_execution_function

log = logging.getLogger("shared")

@exit.exit_wrapper
def runner():
    check_auth()
    with scrape_context_manager():
        with progress_utils.setup_init_live(stop=True):
            if read_args.retriveArgs().scrape_paid:
                progress_utils.update_activity_task(description="Scraping Entire Paid page")
                download_action.scrape_paid_all()

            if not run_action_bool():
                return
            userdata,session=prepare()

            if read_args.retriveArgs().users_first:
                process_users_actions_user_first(userdata,session)
            else:
                process_users_actions(userdata,session)

def run_action_bool():
    return len(read_args.retriveArgs().action)>0

def prepare():
    session=sessionManager.sessionManager(
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
    return userdata,session
@exit.exit_wrapper
@run
async def process_users_actions(userdata=None,session=None):
    user_action_funct=get_user_action_function(process_actions_for_user)
    progress_utils.update_user_activity(description="Users with Actions Completed")
    async with session as c:
        for ele in userdata:
            await user_action_funct(user=ele,c=c)

async def process_actions_for_user(user=None,c=None,*kwargs):
        try:
            all_media, posts,like_posts=await post_media_process(
                user, c=c
            )
            await get_user_action_execution_function(execute_user_action)(all_media, posts,like_posts,ele=user)
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            log.traceback_(f"failed with exception: {e}")
            log.traceback_(traceback.format_exc())
async def execute_user_action(all_media, posts,like_posts,ele=None):
    actions=read_args.retriveArgs().action
    username = ele.name
    model_id = ele.id
    for action in actions:
        if action=="download":
            await download_action.downloader(ele=ele,posts=posts,media=all_media,model_id=model_id,username=username)
        elif action=="like":
            like_action.process_like(ele=ele,posts=like_posts,media=all_media,model_id=model_id,username=username)
        elif action=="unlike":
            like_action.process_unlike(ele=ele,posts=like_posts,media=all_media,model_id=model_id,username=username)




@exit.exit_wrapper
@run
async def process_users_actions_user_first(userdata,session):

    data= await (get_userfirst_data_function(get_users_data_user_first))(userdata,session)
    await get_userfirst_action_execution_function(execute_users_actions_user_first)(data)

async def execute_users_actions_user_first(data):
    progress_utils.update_activity_task(description="Performing Actions on Users")
    progress_utils.update_user_activity(description="Users with Actions completed",completed=0)
    for _, val in data.items():
        all_media = val["media"]
        posts = val["posts"]
        like_posts=val["like_posts"]
        ele=val["ele"]
        await get_user_action_execution_function(execute_user_action)(all_media, posts,like_posts,ele=ele)





async def get_users_data_user_first(userdata,session):
    data={}
    async with session:
        for user in userdata:
                try:
                    with user_first_data_inner_context(session,user):
                        data.update(await process_ele_user_first_data_retriver(user,session))
                except Exception as e:
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())   
        return data



async def process_ele_user_first_data_retriver(ele,session):
    model_id = ele.id
    username = ele.name
    avatar = ele.avatar
    operations.table_init_create(model_id=model_id, username=username)
    media, posts,like_posts = await post_media_process(ele,session)
    return {
            model_id: {
                "username": username,
                "posts": posts,
                "media": media,
                "avatar": avatar,
                "like_posts": like_posts,
                "ele":ele
            }
    }
