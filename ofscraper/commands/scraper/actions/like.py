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
import time




import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.live as progress_utils



log = logging.getLogger("shared")
like_str= "Performing Like Action on {name}"
unlike_str= "Performing Unlike Action on {name}"


@exit.exit_wrapper
def process_like(posts=None,model_id=None,task=None,username=None,**kwargs):
    progress_utils.switch_api_progress()
    progress_utils.update_activity_task(description=like_str.format(name=username))
    logging.getLogger("shared_other").warning(like_str.format(name=username))
    unfavorited_posts = get_posts_for_like(posts)
    posts=pre_filter(posts)
    post_ids = get_post_ids(unfavorited_posts)
    like(model_id, post_ids)


@exit.exit_wrapper
def process_unlike(posts=None,model_id=None,task=None,username=None,**kwargs):
    progress_utils.switch_api_progress()
    progress_utils.update_activity_task(description=unlike_str.format(name=username))
    logging.getLogger("shared_other").warning(unlike_str.format(name=username))
    favorited_posts = get_posts_for_unlike(posts)
    posts=pre_filter(posts)
    post_ids = get_post_ids(favorited_posts)
    unlike(model_id, post_ids)


def get_posts_for_unlike(post):
    return filter_for_favorited(post)


def get_posts_for_like(post):
    return filter_for_unfavorited(post)


def filter_for_unfavorited(posts: list) -> list:
    output = list(filter(lambda x: x.favorited is False and x.opened, posts))
    log.debug(f"[bold]Number of unliked post[/bold] {len(output)}")
    return output


def filter_for_favorited(posts: list) -> list:
    output = list(filter(lambda x: x.favorited is True and x.opened, posts))
    log.debug(f"[bold]Number of liked post[/bold] {len(output)}")
    return output


def pre_filter(posts):
    valid_post = list(filter(lambda x: x.opened and x.responsetype.capitalize() in {"Timeline","Archived","Pinned"},posts))
    seen = set()
    return [
        post for post in valid_post if post.id not in seen and not seen.add(post.id)
    ]


def get_post_ids(posts: list) -> list:
    return list(map(lambda x: x.id, posts))


def like(model_id, ids: list):
    _like(model_id, ids, True)


def unlike(model_id, ids: list):
    _like(model_id, ids, False)


def _like(model_id, ids: list, like_action: bool):
    title = "Liking" if like_action else "Unliking"
    with progress_utils.setup_like_progress_live():
        with sessionManager.sessionManager(
            sem=1,
            backend="httpx",
            retries=constants.getattr("API_LIKE_NUM_TRIES"),
            wait_min=constants.getattr("OF_MIN_WAIT_API"),
            wait_max=constants.getattr("OF_MAX_WAIT_API"),
        ) as c:
            tasks = []
            task=progress_utils.add_like_task(f"{title} posts...\n", total=len(ids))

            [
                tasks.append(functools.partial(_like_request, c, id, model_id))
                for id in ids
            ]
            sleep_duration = 3
            for count, func in enumerate(tasks):
                id = func()
                log.debug(
                    f"ID: {id} Performed {'like' if like_action is True else 'unlike'} action"
                )
                if count + 1 % 60 == 0 and count + 1 % 50 == 0:
                    sleep_duration = 40
                elif count % 60 == 0:
                    sleep_duration = 1  # Divisible by 60 - 1 second sleep
                elif count % 50 == 0:
                    sleep_duration = 30  # Divisible by 50 - 30 seconds sleep
                progress_utils.increment_like_task(task)
                time.sleep(sleep_duration)
            progress_utils.remove_like_task(task)


def _like_request(c, id, model_id):
    with c.requests(
        constants.getattr("favoriteEP").format(id, model_id), method="post"
    ) as _:
        return id
