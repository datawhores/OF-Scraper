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
import os
import platform
import queue
import threading
import time
import timeit
import traceback
from contextlib import contextmanager
from functools import partial

import arrow
import schedule

import ofscraper.actions.like as like
import ofscraper.actions.scraper as OF
import ofscraper.api.init as init
import ofscraper.api.profile as profile
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.filters.media.main as filters
import ofscraper.models.selector as userselector
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.actions as actions
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.auth as auth
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.data as data
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.paths.check as check
import ofscraper.utils.paths.paths as paths
import ofscraper.utils.profiles.manage as profiles_manage
import ofscraper.utils.profiles.tools as profile_tools
import ofscraper.utils.system.network as network

log = logging.getLogger("shared")
count = 0


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


def process_selected_areas():
    log.debug(f"[bold blue] Running Action Mode [/bold blue]")

    global count
    functs = add_selected_areas()
    run_helper(*functs)
    count = 1
    while True:
        if not data.get_InfiniteLoop() or prompts.continue_prompt() == "No":
            break
        action = prompts.action_prompt()
        if action == "main":
            process_prompts()
            break
        elif action == "quit":
            break
        else:
            count > 0 and prompt_reset_helper()
            functs = add_selected_areas()
            run_helper(*functs)
            count = count + 1


def daemon_process():
    functs = add_selected_areas()
    daemon_run_helper(functs)


@exit.exit_wrapper
def process_prompts():
    while True:
        if main_prompt_action():
            break
        elif prompts.continue_prompt() == "No":
            break


def prompt_reset_helper():
    reset = prompts.reset_areas_prompt()
    if reset == "Both":
        actions.remove_download_area()
        actions.remove_like_area()
    elif reset == "Download":
        actions.remove_download_area()
    elif reset == "Like":
        actions.remove_like_area()
    userselector.getselected_usernames(reset=True)


def main_prompt_action():
    global count
    log.debug(f"[bold blue] Running Prompt Menu Mode[/bold blue]")
    while True:
        result_main_prompt = prompts.main_prompt()
        if result_main_prompt == 0:
            action_result_prompt = action_result_helper(prompts.action_prompt())
            if action_result_prompt == 0:
                count > 0 and prompt_reset_helper()
                functs = add_selected_areas()
                run_helper(*functs)
                count = count + 1
            elif action_result_prompt == "quit":
                return True
            elif action_result_prompt == "main":
                continue
        elif result_main_prompt == 1:
            # Edit `auth.json` file
            auth.edit_auth()

        elif result_main_prompt == 2:
            # Edit `data.json` file
            config_.edit_config()

        elif result_main_prompt == 3:
            # Edit `data.json` file
            config_.edit_config_advanced()

        elif result_main_prompt == 4:
            # Display  `Profiles` menu
            result_profiles_prompt = prompts.profiles_prompt()

            if result_profiles_prompt == 0:
                # Change profiles
                profiles_manage.change_profile()

            elif result_profiles_prompt == 1:
                # Edit a profile
                profiles_manage.edit_profile_name()

            elif result_profiles_prompt == 2:
                # Create a new profile

                profiles_manage.create_profile()

            elif result_profiles_prompt == 3:
                # Delete a profile
                profiles_manage.delete_profile()

            elif result_profiles_prompt == 4:
                # View profiles
                profile_tools.print_profiles()
            elif result_profiles_prompt == "quit":
                return True
            elif result_profiles_prompt == "main":
                continue
        elif result_main_prompt == "quit":
            return True


def action_result_helper(input):
    if not input:
        return 0
    elif input == "quit":
        return "quit"
    elif input == "main":
        return "main"


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
    for value in user_dict.values():
        model_id = value[0].post.model_id
        username = value[0].post.username

        operations.create_tables(model_id=model_id, username=username)
        operations.create_backup(model_id, username)
        operations.write_profile_table(model_id=model_id, username=username)
        download.download_picker(
            username,
            model_id,
            value,
        )


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

        if read_args.retriveArgs().scrape_paid:
            user_dict = {}
            [
                user_dict.update(
                    {ele.post.model_id: user_dict.get(ele.post.model_id, []) + [ele]}
                )
                for ele in OF.process_all_paid()
            ]
            for value in user_dict.values():
                try:
                    model_id = value[0].post.model_id
                    username = value[0].post.username
                    log.info(
                        f"inserting {len(value)} items into  into media table for {username}"
                    )
                    operations.batch_mediainsert(
                        value,
                        operations.write_media_table,
                        model_id=model_id,
                        username=username,
                        downloaded=False,
                    )
                    operations.create_tables(model_id=model_id, username=username)
                    operations.create_backup(model_id, username)
                    operations.write_profile_table(model_id=model_id, username=username)
                    download.download_picker(
                        username,
                        model_id,
                        value,
                    )
                except Exception as E:
                    if isinstance(e, KeyboardInterrupt):
                        raise E
                    log.traceback_(f"failed with exception: {E}")
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
                unfavorited_posts = filters.helpers.timeline_array_filter(
                    unfavorited_posts
                )
                log.debug(
                    f"[bold]Number of unliked posts left after date filters[/bold] {len(unfavorited_posts)}"
                )
                post_ids = like.get_post_ids(unfavorited_posts)
                log.debug(
                    f"[bold]Final Number of open and likable post[/bold] {len(post_ids)}"
                )
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
                favorited_posts = filters.helpers.timeline_array_filter(favorited_posts)
                log.debug(
                    f"[bold]Number of liked posts left after date filters[/bold] {len(favorited_posts)}"
                )
                post_ids = like.get_post_ids(favorited_posts)
                log.debug(
                    f"[bold]Final Number of open and unlikable post[/bold] {len(post_ids)}"
                )
                like.unlike(model_id, ele.name, post_ids)


# Adds a function to the job queue
def set_schedule(*functs):
    schedule.every(read_args.retriveArgs().daemon).minutes.do(schedule_helper, functs)
    while len(schedule.jobs) > 0:
        schedule.run_pending()
        time.sleep(30)


def schedule_helper(functs):
    jobqueue.put(logger.start_threads)
    jobqueue.put(logger.updateOtherLoggerStream)
    jobqueue.put(logs.printStartValues)
    jobqueue.put(partial(userselector.getselected_usernames, rescan=True))
    for funct in functs:
        jobqueue.put(funct)
    jobqueue.put(logger.closeThreads)


def daemon_run_helper(*functs):
    global jobqueue
    jobqueue = queue.Queue()
    worker_thread = None
    [jobqueue.put(funct) for funct in functs]
    if read_args.retriveArgs().output == "PROMPT":
        log.info(f"[bold]silent-mode on[/bold]")
    check_auth()
    log.info(f"[bold]Daemon mode on[/bold]")
    userselector.getselected_usernames(rescan=True, reset=True)
    actions.select_areas()
    try:
        worker_thread = threading.Thread(
            target=set_schedule, args=[*functs], daemon=True
        )
        worker_thread.start()
        # Check if jobqueue has function
        while True:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
            log.debug(list(map(lambda x: x, schedule.jobs)))
    except KeyboardInterrupt as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise E
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
            raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise E


def run_helper(*functs):
    # run each function once
    global jobqueue
    jobqueue = queue.Queue()
    [jobqueue.put(funct) for funct in functs]
    if read_args.retriveArgs().output == "PROMPT":
        log.info(f"[bold]silent-mode on[/bold]")
    try:
        for _ in functs:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
        dates.resetLogdate()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                schedule.clear()
                raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E


def check_auth():
    status = None
    while status != "UP":
        status = init.getstatus()
        if status == "DOWN":
            log.warning("Auth Failed")
            auth.make_auth(auth=auth.read_auth())
            continue
        break


def check_config():
    while not check.mp4decryptchecker(data.get_mp4decrypt()):
        console.get_shared_console().print(
            "There is an issue with the mp4decrypt path\n\n"
        )
        log.debug(f"[bold]current mp4decrypt path[/bold] {data.get_mp4decrypt()}")
        config_.update_mp4decrypt()
    while not check.ffmpegchecker(data.get_ffmpeg()):
        console.get_shared_console().print("There is an issue with the ffmpeg path\n\n")
        log.debug(f"[bold]current ffmpeg path[/bold] {data.get_ffmpeg()}")
        config_.update_ffmpeg()
    log.debug(f"[bold]final mp4decrypt path[/bold] {data.get_mp4decrypt()}")
    log.debug(f"[bold]final ffmpeg path[/bold] {data.get_ffmpeg()}")


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


def print_start():
    with stdout.lowstdout():
        console.get_shared_console().print(
            f"[bold green] Welcome to OF-Scraper Version {read_args.retriveArgs().version}[/bold green]"
        )


def main():
    try:
        print_start()
        paths.cleanup()
        paths.cleanDB()
        network.check_cdm()

        scrapper()
        paths.cleanup()
        paths.cleanDB()
    except KeyboardInterrupt:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.cleanup()
                paths.cleanDB()
                raise KeyboardInterrupt
        except KeyboardInterrupt:
            raise KeyboardInterrupt
    except Exception as E:
        try:
            with exit.DelayedKeyboardInterrupt():
                paths.cleanup()
                paths.cleanDB()
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                raise E


def scrapper():
    if platform.system() == "Windows":
        os.system("color")
    global selectedusers
    selectedusers = None
    args = read_args.retriveArgs()
    if args.daemon:
        if len(args.action) == 0 and not args.scrape_paid:
            prompts.action_prompt()
        check_auth()
        check_config()
        daemon_process()
    elif len(args.action) > 0:
        check_auth()
        check_config()
        process_selected_areas()
    elif len(args.action) == 0:
        process_prompts()
