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

import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.me as me_util


def separate_by_id(data: list, media_ids: list) -> list:
    media_ids = set(media_ids)
    return list(filter(lambda x: x.id not in media_ids, data))


def seperate_avatars(data):
    return list(filter(lambda x: seperate_avatar_helper(x) is False, data))


def seperate_avatar_helper(ele):
    # id for avatar comes from xxh32 of url
    if ele.postid and ele.responsetype == "profile":
        value = cache.get(ele.postid, default=False)

        return value
    return False


def seperate_by_self(data):
    my_id = me_util.get_id()
    if constants.getattr("FILTER_SELF_MEDIA"):
        return list(filter(lambda x: x.post.fromuser != my_id, data))
