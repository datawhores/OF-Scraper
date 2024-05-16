import logging
import time
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
import ofscraper.utils.live as progress_utils
from ofscraper.commands.scraper.scrape_context import scrape_context_manager
from ofscraper.commands.scraper.post import post_media_process
import ofscraper.commands.scraper.actions.download as download_action
import ofscraper.commands.scraper.actions.like as like_action


log = logging.getLogger("shared")

@exit.exit_wrapper
def runner():
    with scrape_context_manager():
        with progress_utils.setup_api_split_progress_live(stop=True):
            if read_args.retriveArgs().users_first:
                user_first()
            else:
                normal()

def normal():
    actions=read_args.retriveArgs().action
    if read_args.retriveArgs().scrape_paid:
        download_action.scrape_paid_all()
    if len(actions)==0:
        return
    progress_utils.live.start()
    download_action.unique_name_warning()
    profile_tools.print_current_profile()
    init.print_sign_status()
    userdata = userselector.getselected_usernames(rescan=False)
    length = len(userdata)
    session = sessionManager.sessionManager(
        sem=constants.getattr("API_REQ_SEM_MAX"),
        retries=constants.getattr("API_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )
    task = progress_utils.username_progress.add_task(
                "Data Retrival+Downloading", total=length
    )
    for count,ele in enumerate(userdata):
        username = ele.name
        model_id = ele.id
        avatar=ele.avatar
        active=ele.active
        
        progress_utils.switch_api_progress()
        logging.getLogger("shared_other").warning(download_action.progress_str.format(count=count+1,length=length))
        logging.getLogger("shared_other").warning( download_action.data_str.format(name=username))
        progress_utils.username_progress.update(task,description= download_action.data_str.format(name=username))
        try:
            if constants.getattr("SHOW_AVATAR") and avatar:
                logging.getLogger("shared_other").warning(download_action.avatar_str.format(avatar=avatar))
            logging.getLogger("shared_other").warning(
                download_action.area_str.format(areas=",".join(areas.get_download_area()),name=username,active=active
            ))
            progress_utils.username_progress.update(task,description=download_action.area_str.format(areas=",".join(areas.get_download_area()),name=username,active=active))

            all_media, posts,like_posts= post_media_process(
                ele, session=session
            )
            for action in actions:
                if action=="download":
                    download_action.downloader(ele=ele,posts=posts,media=all_media,task=task,model_id=model_id)
                elif action=="like":
                    like_action.process_like(ele=ele,posts=like_posts,media=all_media,task=task,model_id=model_id)
                elif action=="unlike":
                    like_action.process_unlike(ele=ele,posts=like_posts,media=all_media,task=task,model_id=model_id)
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            log.traceback_(f"failed with exception: {e}")
            log.traceback_(traceback.format_exc())
            
            
@exit.exit_wrapper
def user_first():
    userdata=userselector.getselected_usernames(rescan=False)
    actions=read_args.retriveArgs().action

    length=len(userdata)
    task=progress_utils.username_progress.add_task("Data Retrival",total=length)

    session=sessionManager.sessionManager(
    sem=constants.getattr("API_REQ_SEM_MAX"),
    retries=constants.getattr("API_NUM_TRIES"),
    wait_min=constants.getattr("OF_MIN_WAIT_API"),
    wait_max=constants.getattr("OF_MAX_WAIT_API"),
    total_timeout=constants.getattr("API_TIMEOUT_PER_TASK"),
    )
    data={}

    if read_args.retriveArgs().scrape_paid:
        download_action.scrape_paid_all()
    
    for count,user in enumerate(userdata):
        progress_utils.switch_api_progress()
        progress_utils.username_progress.update(task,description=f"Data Retrival on {user.name}",advance=1)
        logging.getLogger("shared_other").warning(f"\[{user.name}] Data Retrival Progress: {count+1}/{length} models")
        data.update(process_user_first_data_retriver(user,session=session))
        if count==5:
            break
        progress_utils.username_progress.remove(task)
    for model_id, val in data.items():
        all_media = val["media"]
        posts = val["posts"]
        like_posts=val["like_posts"]
        ele=val["ele"]
        for action in actions:
            if action=="download":
                download_action.downloader(ele=ele,posts=posts,media=all_media,task=task,model_id=model_id)
            elif action=="like":
                like_action.process_like(ele=ele,posts=like_posts,media=all_media,task=task,model_id=model_id)
            elif action=="unlike":
                like_action.process_unlike(ele=ele,posts=like_posts,media=all_media,task=task,model_id=model_id)

def process_user_first_data_retriver(ele,session=None,live=None):
    model_id = ele.id
    username = ele.name
    avatar = ele.avatar
    active= ele.active
    if constants.getattr("SHOW_AVATAR") and avatar:
        logging.getLogger("shared_other").warning(download_action.avatar_str.format(avatar))
    if bool(areas.get_download_area()):
        logging.getLogger("shared_other").info(
             download_action.format(areas=",".join(areas.get_download_area()),name=username,active=active
                )
        )
    operations.table_init_create(model_id=model_id, username=username)
    media, posts,like_posts = post_media_process(ele,session=session,live=live)
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
