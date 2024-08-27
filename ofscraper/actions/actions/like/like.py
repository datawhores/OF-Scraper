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

import functools
import logging
import random
import time

import  ofscraper.runner.manager as manager2
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater

from ofscraper.classes.sessionmanager.sessionmanager import SessionSleep

log = logging.getLogger("shared")
warning_str = "\n[red]Current Like rate can eat through the ~1000 like limit in ~1 hour\nIncreasing the rate could lead to getting logged out[/red]"
like_str = "Performing Like Action on {name}" + warning_str
unlike_str = "Performing Unlike Action on {name}" + warning_str


@exit.exit_wrapper
def process_like(posts=None, model_id=None, task=None, username=None, **kwargs):
    progress_utils.switch_api_progress()
    progress_updater.update_activity_task(description=like_str.format(name=username))
    logging.getLogger("shared_other").warning(like_str.format(name=username))
    unfavorited_posts = get_posts_for_like(posts)
    posts = pre_filter(posts)
    post_ids = get_post_ids(unfavorited_posts)
    return like(model_id, username, post_ids)


@exit.exit_wrapper
def process_unlike(posts=None, model_id=None, task=None, username=None, **kwargs):
    progress_utils.switch_api_progress()
    progress_updater.update_activity_task(description=unlike_str.format(name=username))
    logging.getLogger("shared_other").warning(unlike_str.format(name=username))
    favorited_posts = get_posts_for_unlike(posts)
    posts = pre_filter(posts)
    post_ids = get_post_ids(favorited_posts)
    return unlike(model_id, username, post_ids)


def get_posts_for_unlike(post):
    return filter_for_favorited(post)


def get_posts_for_like(post):
    return filter_for_unfavorited(post)


def filter_for_unfavorited(posts: list) -> list:
    # output = list(filter(lambda x: x.favorited is False and x.opened, posts))
    output = list(filter(lambda x: x.opened, posts))

    log.debug(f"[bold]Number of unliked post[/bold] {len(output)}")
    return output


def filter_for_favorited(posts: list) -> list:
    # output = list(filter(lambda x: x.favorited is True and x.opened, posts))
    output = list(filter(lambda x: x.opened, posts))

    log.debug(f"[bold]Number of liked post[/bold] {len(output)}")
    return output


def pre_filter(posts):
    seen = set()
    return [post for post in posts if post.id not in seen and not seen.add(post.id)]


def get_post_ids(posts: list) -> list:
    return list(map(lambda x: x.id, posts))


def like(model_id, username, ids: list):
    return _like(model_id, username, ids, True)


def unlike(model_id, username, ids: list):
    return _like(model_id, username, ids, False)


def _like(model_id, username, ids: list, like_action: bool):
    like_str = (
        "Posts toggled from unlike to like...\n"
        if like_action
        else "Posts toggled from like to unlike...\n"
    )

    like_func = _toggle_like_requests if like_action else _toggle_unlike_requests
    with progress_utils.setup_like_progress_live():
        with manager2.Manager.get_ofsession(
            sem_count=1,
            backend="httpx",
            retries=constants.getattr("API_LIKE_NUM_TRIES"),
        ) as c:
            tasks = []
            task = progress_updater.add_like_task("checked posts...\n", total=len(ids))
            task2 = progress_updater.add_like_task(like_str, total=None)

            [tasks.append(functools.partial(like_func, c, id, model_id)) for id in ids]
            max_duration = constants.getattr("MAX_SLEEP_DURATION_LIKE")
            min_duration = constants.getattr("MIN_SLEEP_DURATION_LIKE")
            failed = 0
            post = 0
            liked = 0

            for _, func in enumerate(tasks):
                out = func()
                post += 1
                # no sleep if cache
                if out == 0:
                    sleep_duration = 0
                # random sleep else
                else:
                    sleep_duration = random.uniform(min_duration, max_duration)
                # if toggled once
                if out == 1:
                    liked = +1
                    progress_updater.increment_like_task(task2)
                # if failed
                elif out == 3:
                    failed += 1
                progress_updater.increment_like_task(task)
                time.sleep(sleep_duration)
            progress_updater.remove_like_task(task)
            progress_updater.remove_like_task(task2)
        return get_final_like_log(like_action, username, failed, post, liked)


def get_final_like_log(like_action, username, failed, post, liked):
    title = "Liked" if like_action else "Unliked"
    action = title.lower()
    unchanged = post - failed - liked

    liked_changed_log = (
        f"{liked} post changed to {action}"
        if liked == 0
        else f"[green]{liked} post changed to {action}[/green]"
    )
    like_unchanged_log = (
        f"{unchanged} posts not changed"
        if unchanged == 0
        else f"[yellow]{unchanged} post not changed[/yellow]"
    )
    failed_log = "0 post failed" if failed == 0 else f"[red]{failed} post failed[/red]"
    post_check_log = f"{post} posts checked and kept at {action}"

    text_out = ""
    if post == 0:
        text_out = f"[bold]\\[{username}][/bold] [bold][Action {title}][/bold] \\[{post_check_log}, ({liked_changed_log}, {like_unchanged_log}), {failed_log}]"
        log.warning(text_out)
    else:
        text_out = f"[deep_sky_blue2][bold]\\[{username}][/bold] [bold][Action {title}][/bold] [[yellow]{post_check_log}[/yellow], ({liked_changed_log}, {like_unchanged_log}), {failed_log}][/deep_sky_blue2]"
        log.warning(text_out)
    return text_out


def _toggle_like_requests(c, id, model_id):

    sleeper = SessionSleep(
        sleep=constants.getattr("SESSION_429_SLEEP_STARTER_VAL"),
        difmin=constants.getattr("SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF"),
    )
    if not read_args.retriveArgs().force_like and cache.get(f"liked_status_{id}", None):
        log.debug(f"ID: {id} marked as liked in cache")
        return 0
    max_duration = constants.getattr("MAX_SLEEP_DURATION_LIKE")
    min_duration = constants.getattr("MIN_SLEEP_DURATION_LIKE")

    sleep_duration = random.uniform(min_duration, max_duration)
    favorited, id = _like_request(c, id, model_id, sleeper)
    if favorited is None:
        return 3
    elif favorited:
        log.debug(f"ID: {id} changed to liked")
        out = 1
    else:
        log.debug(f"ID: {id} restored to liked")
        time.sleep(sleep_duration)
        _like_request(c, id, model_id, sleeper)
        out = 2
    cache.set(f"liked_status_{id}", True)
    return out


def _toggle_unlike_requests(c, id, model_id):
    sleeper = SessionSleep(
        sleep=constants.getattr("SESSION_429_SLEEP_STARTER_VAL"),
        difmin=constants.getattr("SESSION_429_LIKE_INCREASE_SLEEP_TIME_DIF"),
    )
    if (
        not read_args.retriveArgs().force_like
        and cache.get(f"liked_status_{id}", None) is False
    ):
        log.debug(f"ID: {id} marked as unliked in cache")
        return 0
    sleep_duration = constants.getattr("DOUBLE_TOGGLE_SLEEP_DURATION_LIKE")
    favorited, id = _like_request(c, id, model_id, sleeper)
    if favorited is None:
        return 3
    elif favorited is False:
        log.debug(f"ID: {id} changed to unliked")
        out = 1
    else:
        log.debug(f"ID: {id} restored to unlike")
        time.sleep(sleep_duration)
        _like_request(c, id, model_id, sleeper)
        out = 2
    cache.set(f"liked_status_{id}", False)
    return out


def _like_request(c, id, model_id, sleeper):

    with c.requests(
        constants.getattr("favoriteEP").format(id, model_id),
        method="post",
        sleeper=sleeper,
        retries=constants.getattr("LIKE_MAX_RETRIES"),
    ) as r:
        try:
            return r.json_()["isFavorite"], r.json_()["id"]
        except:
            return None
