r"""
                                                             
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
import time
import traceback
from contextlib import contextmanager

import ofscraper.api.init as init
import ofscraper.api.profile as profile
import ofscraper.classes.models as models
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.actions.download.post as OF
import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.models.selector as userselector
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.commands.actions.scrape_context import scrape_context_manager

log = logging.getLogger("shared")


@exit.exit_wrapper
def process_post():
    if read_args.retriveArgs().users_first:
        process_post_user_first()
    else:
        normal_post_process()


@exit.exit_wrapper
def process_post_user_first():
    with scrape_context_manager():
        unique_name_warning()
        profile_tools.print_current_profile()
        init.print_sign_status()
        data = {}
        for user in userselector.getselected_usernames(rescan=False):
            data.update(process_user_first_data_retriver(user))
        length=len(list(data.keys()))
        count=0
        for model_id, val in data.items():
            username=val["username"]
            media=val['media']
            avatar=val['avatar']
            posts=val['posts']
            try:
                log.warning(
                f"Download action progressing on model {count+1}/{length} models "
                )
                if constants.getattr("SHOW_AVATAR") and avatar:
                    log.warning(f"Avatar : {avatar}")
                    download.download_process(
                        username, model_id, media,
                        posts=posts
                    )
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
    if constants.getattr("SHOW_AVATAR") and avatar:
        log.warning(f"Avatar : {avatar}")
    if bool(areas.get_download_area()):
        log.info(
            f"Getting {','.join(areas.get_download_area())} for [bold]{ele.name}[/bold]\n[bold]Subscription Active:[/bold] {ele.active}"
        )
    try:
        operations.table_init_create(model_id=model_id, username=username)
        media, posts = OF.process_areas(ele, model_id,username)
        return {model_id: {"username": username, "posts": posts, "media": media,"avatar":avatar}}
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())


def scrape_paid_all(user_dict=None):
    user_dict = OF.process_all_paid()
    oldUsers = userselector.get_ALL_SUBS_DICT()
    length = len(list(user_dict.keys()))
    for count, value in enumerate(user_dict.values()):
        model_id = value["model_id"]
        username = value["username"]
        posts = value["posts"]
        medias = value["medias"]
        log.warning(
            f"Download paid content for {model_id}_{username} number:{count+1}/{length} models "
        )
        userselector.set_ALL_SUBS_DICTVManger(
            {username: models.Model(profile.scrape_profile(model_id))}
        )
        download.download_process(username, model_id, medias, posts=posts)
    # restore og users
    userselector.set_ALL_SUBS_DICT(oldUsers)


@exit.exit_wrapper
def normal_post_process():
    with scrape_context_manager():
        unique_name_warning()
        profile_tools.print_current_profile()
        init.print_sign_status()
        userdata = userselector.getselected_usernames(rescan=False)
        length = len(userdata)
        for count, ele in enumerate(userdata):
            log.warning(
                f"Download action progressing on model {count+1}/{length} models "
            )
            if constants.getattr("SHOW_AVATAR") and ele.avatar:
                log.warning(f"Avatar : {ele.avatar}")
            log.warning(
                f"Getting {','.join(areas.get_download_area())} for [bold]{ele.name}[/bold]\n[bold]Subscription Active:[/bold] {ele.active}"
            )
            try:
                model_id = ele.id
                username = ele.name
                operations.table_init_create(model_id=model_id, username=username)
                combined_urls, posts = OF.process_areas(ele, model_id,username)
                download.download_process(
                    username, model_id, combined_urls, posts=posts
                )
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())

def unique_name_warning():
    if not placeholder.check_uniquename():
            log.warning(
                "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
            )
            time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)