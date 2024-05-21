import logging
import traceback

import ofscraper.api.init as init
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.db.operations as operations
import ofscraper.models.selector as userselector
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.utils.live.live as progress_utils
from ofscraper.commands.scraper.scrape_context import scrape_context_manager
from ofscraper.commands.scraper.post import post_media_process
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.commands.scraper.actions.like as like_action
from ofscraper.utils.context.run_async import run
from ofscraper.utils.checkers import check_auth


from ofscraper.commands.helpers.context import user_first_data_inner_context,user_first_action_runner_inner_context,user_first_action_runner_outer_context

from ofscraper.commands.helpers.shared import user_first_data_preparer
log = logging.getLogger("shared")

@exit.exit_wrapper
def runner():
    check_auth()
    with scrape_context_manager():
        userdata,actions,session=prepare()
        with progress_utils.setup_api_split_progress_live(stop=True):
            if read_args.retriveArgs().scrape_paid:
                progress_utils.update_activity_task(description="Scraping Entire Paid page")
                download_action.scrape_paid_all()
        
            if read_args.retriveArgs().users_first:
                user_first(userdata,actions,session)
            elif bool(actions):
                normal(userdata,actions,session)


def prepare():
    session=sessionManager.sessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        retries=constants.getattr("API_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    ) 
    actions=read_args.retriveArgs().action
    userdata=None
    if len(actions)==0:
        return userdata,actions,session

    download_action.unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    userdata = userselector.getselected_usernames(rescan=False)
    return userdata,actions,session
@exit.exit_wrapper
@run
async def normal(userdata,actions,session):
    length=len(userdata)
    progress_utils.update_activity_count(description="Users with Actions Completed")
    async with session as c:
        for count,ele in enumerate(userdata):
            username = ele.name
            model_id = ele.id
            avatar=ele.avatar
            active=ele.active
            try:
                async with user_first_data_context(session,length,count,areas,ele):

                    all_media, posts,like_posts=await post_media_process(
                        ele, c=c
                    )
                    for action in actions:
                        if action=="download":
                            await download_action.downloader(ele=ele,posts=posts,media=all_media,model_id=model_id,username=username)
                        elif action=="like":
                            like_action.process_like(ele=ele,posts=like_posts,media=all_media,model_id=model_id,username=username)
                        elif action=="unlike":
                            like_action.process_unlike(ele=ele,posts=like_posts,media=all_media,model_id=model_id,username=username)
                    progress_utils.increment_activity_count()


            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())

@exit.exit_wrapper
def user_first(userdata,actions,session):
    data=user_first_data_retriver(userdata,session)
    user_first_action_runner(data,actions)
@run
async def user_first_action_runner(data,actions):
    with user_first_action_runner_outer_context():
        progress_utils.update_activity_task(description="Performing Actions on Users")
        progress_utils.update_user_first_activity(description="Users with Actions completed",completed=0)
        for model_id, val in data.items():
            all_media = val["media"]
            posts = val["posts"]
            like_posts=val["like_posts"]
            ele=val["ele"]
            username=val["username"]
            with user_first_action_runner_inner_context(val["avatar"]):
                try:
                    for action in actions:
                        if action=="download":
                            await download_action.downloader(ele=ele,posts=posts,media=all_media,model_id=model_id,username=username)
                        elif action=="like":
                            like_action.process_like(ele=ele,posts=like_posts,media=all_media,model_id=model_id,username=username)
                        elif action=="unlike":
                            like_action.process_unlike(ele=ele,posts=like_posts,media=all_media,model_id=model_id,username=username)
                    progress_utils.increment_user_first_activity()
                except Exception as e:
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())



@run
async def user_first_data_retriver(userdata,session):
    data={}
    length=len(userdata)
    user_first_data_preparer()
    async with session:
        for count,user in enumerate(userdata):
                try:
                    with user_first_data_inner_context(session,length,count,user):
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
