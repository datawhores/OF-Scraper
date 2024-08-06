from ofscraper.data.api.common.cache.read import read_check_mode
from ofscraper.data.api.common.cache.write import set_check_mode_posts


def update_check(unduped, model_id, after, API):
    if not after:
        seen = set()
        all_posts = [
            post
            for post in read_check_mode(model_id, API) + unduped
            if post["id"] not in seen and not seen.add(post["id"])
        ]
        set_check_mode_posts(model_id, API, all_posts)


def set_check(posts, model_id, API):
    set_check_mode_posts(model_id, API, posts)


def reset_check(model_id, API):
    set_check_mode_posts(model_id, API, [])


def read_check(model_id, API):
    return read_check_mode(model_id, API)
