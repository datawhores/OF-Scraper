from ofscraper.data.api.common.cache.read import read_check_mode
from ofscraper.data.api.common.cache.write import set_check_mode_posts


def update_check(unduped, model_id, after, API):
    if not after:
        seen = set()
        all_posts = [
            post
            for post in unduped + (read_check_mode(model_id, API) or [])
            if post["id"] not in seen and not seen.add(post["id"])
        ]
        # update=True means "Do NOT reset the 3-day expiration timer"
        set_check_mode_posts(model_id, API, all_posts, update=True)


def set_check(posts, model_id, API):
    # update=False means "I fetched this fresh, start a new 3-day timer"
    set_check_mode_posts(model_id, API, posts, update=False)


def reset_check(model_id, API):
    set_check_mode_posts(model_id, API, [], update=False)


def read_check(model_id, API):
    return read_check_mode(model_id, API)