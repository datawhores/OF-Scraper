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

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.me as me_util
from ofscraper.utils.cache.profile import is_profile_cached


def separate_by_id(data: list, media_ids: list) -> list:
    media_ids = set(media_ids)
    return list(filter(lambda x: x.id not in media_ids, data))


def seperate_avatars(data):
    return list(filter(lambda x: seperate_avatar_helper(x) is False, data))


def seperate_avatar_helper(ele):
    return is_profile_cached(ele)


def seperate_by_self(data):
    my_id = me_util.get_id()
    if of_env.getattr("FILTER_SELF_MEDIA"):
        return list(filter(lambda x: x.post.fromuser != my_id, data))
    return data
