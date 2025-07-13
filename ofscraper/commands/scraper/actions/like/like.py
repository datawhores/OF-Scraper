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

import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.classes.of.posts import Post

log = logging.getLogger("shared")
warning_str = "\n[red]Current Like rate can eat through the ~1000 like limit in ~1 hour\nIncreasing the rate could lead to getting logged out[/red]"
like_str = "Performing Like Action on {name}" + warning_str
unlike_str = "Performing Unlike Action on {name}" + warning_str


@exit.exit_wrapper
def process_like(posts=None, model_id=None, username=None, **kwargs):
    with progress_utils.setup_live("like"):
        progress_updater.activity.update_task(
            description=like_str.format(name=username), visible=True
        )
        logging.getLogger("shared").warning(like_str.format(name=username))
        like(model_id, username, posts)


@exit.exit_wrapper
def process_unlike(posts=None, model_id=None, username=None, **kwargs):
    with progress_utils.setup_live("like"):
        progress_updater.activity.update_task(
            description=unlike_str.format(name=username), visible=True
        )
        logging.getLogger("shared").warning(unlike_str.format(name=username))
        unlike(model_id, username, posts)


def get_posts_for_unlike(post):
    return filter_for_favorited(post)


def get_posts_for_like(post):
    return filter_for_unfavorited(post)


def filter_for_unfavorited(posts: list) -> list:
    output = list(filter(lambda x: x.opened, posts))

    log.debug(f"[bold]Number of unliked post[/bold] {len(output)}")
    return output


def filter_for_favorited(posts: list) -> list:
    output = list(filter(lambda x: x.opened, posts))

    log.debug(f"[bold]Number of liked post[/bold] {len(output)}")
    return output


def like(model_id, username, posts: list[Post]):
    return _like(model_id, username, posts, True)


def unlike(model_id, username, posts: list):
    return _like(model_id, username, posts, False)


def _like(model_id, username, posts: list, like_action: bool):
    like_str = (
        "Posts toggled from unlike to like...\n"
        if like_action
        else "Posts toggled from like to unlike...\n"
    )

    like_func = _toggle_like_requests if like_action else _toggle_unlike_requests
    with progress_utils.setup_live("like"):
        with manager.Manager.get_like_session(
            sem_count=1,
            retries=of_env.getattr("API_LIKE_NUM_TRIES"),
        ) as c:
            tasks = []
            task = progress_updater.like.add_overall_task(
                "checked posts...\n", total=len(posts)
            )
            task2 = progress_updater.like.add_overall_task(like_str, total=None)

            [
                tasks.append(functools.partial(like_func, c, post, model_id))
                for post in posts
            ]
            max_duration = of_env.getattr("MAX_SLEEP_DURATION_LIKE")
            min_duration = of_env.getattr("MIN_SLEEP_DURATION_LIKE")

            for _, func in enumerate(tasks):
                out = func()
                sleep_duration = random.uniform(min_duration, max_duration)
                if out == 1:
                    progress_updater.like.update_overall_task(task2, advance=1)
                progress_updater.like.update_overall_task(task, advance=1)
                time.sleep(sleep_duration)
            progress_updater.like.remove_overall_task(task)
            progress_updater.like.remove_overall_task(task2)


def _toggle_like_requests(c, post: Post, model_id):
    max_duration = of_env.getattr("MAX_SLEEP_DURATION_LIKE")
    min_duration = of_env.getattr("MIN_SLEEP_DURATION_LIKE")
    post.mark_like_attempt()

    sleep_duration = random.uniform(min_duration, max_duration)
    favorited, id = _like_request(c, post.id, model_id)
    if favorited is None:
        post.mark_post_liked(success=False)
        return 3
    elif favorited:
        log.debug(f"ID: {id} changed to liked")
        post.mark_post_liked()
        return 1
    else:
        log.debug(f"ID: {id} restored to liked")
        time.sleep(sleep_duration)
        _like_request(c, id, model_id)
        post.mark_post_liked()
        return 2


def _toggle_unlike_requests(c, post: Post, model_id):
    sleep_duration = of_env.getattr("DOUBLE_TOGGLE_SLEEP_DURATION_LIKE")
    post.mark_like_attempt()

    favorited, id = _like_request(c, post.id, model_id)
    if favorited is None:
        post.mark_post_unliked(success=False)
        return 3
    elif favorited is False:
        log.debug(f"ID: {id} changed to unliked")
        post.mark_post_unliked()
        return 1
    else:
        log.debug(f"ID: {id} restored to unlike")
        time.sleep(sleep_duration)
        _like_request(c, id, model_id)
        post.mark_post_unliked()
        return 2


def _like_request(c, id, model_id):

    with c.requests(
        of_env.getattr("favoriteEP").format(id, model_id),
        method="post",
        retries=of_env.getattr("LIKE_MAX_RETRIES"),
    ) as r:
        try:
            return r.json_()["isFavorite"], r.json_()["id"]
        except:
            return None
