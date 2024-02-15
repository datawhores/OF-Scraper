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
import timeit
import traceback
from contextlib import contextmanager

import arrow

import ofscraper.actions.like as like
import ofscraper.actions.scraper as OF
import ofscraper.api.init as init
import ofscraper.api.profile as profile
import ofscraper.classes.models as models
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.filters.media.main as filters
import ofscraper.models.selector as userselector
import ofscraper.models.selector as selector
import ofscraper.utils.actions as actions
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.profiles.tools as profile_tools

log = logging.getLogger("shared")


@contextmanager
def scrape_context_manager():
    # reset stream if needed
    # Before yield as the enter method
    start = timeit.default_timer()
    log.warning(
        f"""
==============================                            
[bold] starting script [/bold]
==============================
"""
    )
    yield
    end = timeit.default_timer()
    log.warning(
        f"""
===========================
[bold] Script Finished [/bold]
Run Time:  [bold]{str(arrow.get(end)-arrow.get(start)).split(".")[0]}[/bold]
===========================
"""
    )


@exit.exit_wrapper
def process_post():
    if read_args.retriveArgs().users_first:
        process_post_user_first()
    else:
        normal_post_process()


@exit.exit_wrapper
def process_post_user_first():
    with scrape_context_manager():
        if not placeholder.Placeholders().check_uniquename():
            log.warning(
                "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]      \
            "
            )
            time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)

        profile_tools.print_current_profile()
        init.print_sign_status()
        userdata = userselector.getselected_usernames(rescan=False)
        length = len(userdata)
        output = []

        for count, ele in enumerate(userdata):
            log.info(f"Data retrival progressing on model {count+1}/{length}")
            if constants.getattr("SHOW_AVATAR") and ele.avatar:
                log.warning(f"Avatar : {ele.avatar}")
            if bool(areas.get_download_area()):
                log.info(
                    f"Getting {','.join(areas.get_download_area())} for [bold]{ele.name}[/bold]\n[bold]Subscription Active:[/bold] {ele.active}"
                )
            try:
                model_id = ele.id
                operations.write_profile_table(model_id=model_id, username=ele.name)
                output.extend(OF.process_areas(ele, model_id))
                #
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())


def scrape_paid(user_dict=None):
    output = []
    user_dict = user_dict or {}
    output.extend(OF.process_all_paid())
    user_dict = user_dict or {}
    [
        user_dict.update(
            {ele.post.model_id: user_dict.get(ele.post.model_id, []) + [ele]}
        )
        for ele in output
    ]
    oldUsers = selector.get_ALL_SUBS_DICT()
    for value in user_dict.values():
        model_id = value[0].post.model_id
        username = value[0].post.username
        selector.set_ALL_SUBS_DICTVManger(
            {username: models.Model(profile.scrape_profile(model_id))}
        )
        operations.create_tables(model_id=model_id, username=username)
        operations.create_backup(model_id, username)
        operations.write_profile_table(model_id=model_id, username=username)
        download.download_picker(
            username,
            model_id,
            value,
        )
    # restore og users
    selector.set_ALL_SUBS_DICT(oldUsers)


@exit.exit_wrapper
def normal_post_process():
    with scrape_context_manager():
        if not placeholder.Placeholders().check_uniquename():
            log.warning(
                "[red]Warning: Your generated filenames may not be unique\n \
            https://of-scraper.gitbook.io/of-scraper/config-options/customizing-save-path#warning[/red]     \
            "
            )
            time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT") * 3)
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
                operations.create_tables(model_id, ele.name)
                operations.create_backup(model_id, ele.name)
                operations.write_profile_table(model_id=model_id, username=ele.name)
                combined_urls = OF.process_areas(ele, model_id)
                download.download_picker(ele.name, model_id, combined_urls)
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    raise e
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())


@exit.exit_wrapper
def process_like():
    with scrape_context_manager():
        profile_tools.print_current_profile()
        init.print_sign_status()
        userdata = userselector.getselected_usernames(rescan=False)
        active = list(filter(lambda x: x.active, userdata))
        length = len(active)
        log.debug(f"Number of Active Accounts selected {length}")
        with stdout.lowstdout():
            for count, ele in enumerate(active):
                log.info(f"Like action progressing on model {count+1}/{length}")
                if constants.getattr("SHOW_AVATAR") and ele.avatar:
                    log.warning(f"Avatar : {ele.avatar}")
                log.warning(
                    f"Getting {','.join(areas.get_like_area())} for [bold]{ele.name}[/bold]\n[bold]Subscription Active:[/bold] {ele.active}"
                )
                model_id = ele.id
                operations.create_tables(model_id, ele.name)
                operations.create_backup(model_id, ele.name)
                unfavorited_posts = like.get_post_for_like(model_id, ele.name)
                unfavorited_posts = filters.media_filter_for_like(
                    unfavorited_posts, like=True
                )
                post_ids = like.get_post_ids(unfavorited_posts)
                like.like(model_id, ele.name, post_ids)


@exit.exit_wrapper
def process_unlike():
    with scrape_context_manager():
        profile_tools.print_current_profile()
        init.print_sign_status()
        userdata = userselector.getselected_usernames(rescan=False)
        active = list(filter(lambda x: x.active, userdata))
        length = len(active)
        log.debug(f"Number of Active Accounts selected {length}")
        with stdout.lowstdout():
            for count, ele in enumerate(active):
                log.info(f"Unlike action progressing on model {count+1}/{length}")
                if constants.getattr("SHOW_AVATAR") and ele.avatar:
                    log.warning(f"Avatar : {ele.avatar}")
                log.warning(
                    f"Getting {','.join(areas.get_like_area())} for [bold]{ele.name}[/bold]\n[bold]Subscription Active:[/bold] {ele.active}"
                )
                model_id = profile.get_id(ele.name)
                operations.create_tables(model_id, ele.name)
                operations.create_backup(model_id, ele.name)
                favorited_posts = like.get_posts_for_unlike(model_id, ele.name)
                favorited_posts = filters.media_filter_for_like(
                    favorited_posts, like=False
                )
                post_ids = like.get_post_ids(favorited_posts)
                like.unlike(model_id, ele.name, post_ids)


def add_selected_areas():
    functs = []
    action = read_args.retriveArgs().action
    if "like" in action and "download" in action:
        actions.select_areas()
        functs.append(process_post)
        functs.append(process_like)
    elif "unlike" in action and "download" in action:
        actions.select_areas()
        functs.append(process_post)
        functs.append(process_unlike)
    elif "download" in action:
        actions.select_areas()
        functs.append(process_post)
    elif "like" in action:
        actions.select_areas()
        functs.append(process_like)
    elif "unlike" in action:
        actions.select_areas()
        functs.append(process_unlike)
    if read_args.retriveArgs().scrape_paid:
        functs.append(scrape_paid)
    return functs
