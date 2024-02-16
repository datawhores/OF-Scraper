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


def separate_by_id(data: list, media_ids: list) -> list:
    media_ids = set(media_ids)
    return list(filter(lambda x: x.id not in media_ids, data))


def seperate_avatars(data):
    return list(filter(lambda x: seperate_avatar_helper(x) == False, data))


def seperate_avatar_helper(ele):
    # id for avatar comes from xxh32 of url
    if ele.postid and ele.responsetype == "profile":
        value = cache.get(ele.postid, default=False)
        cache.close()
        return value
    return False


# def separate_database_results_by_id(results: list, media_ids: list) -> list:
#     filtered_results = [r for r in results if r[0] not in media_ids]
#     return filtered_results
