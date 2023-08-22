r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
from ..utils.paths import getcachepath
from diskcache import Cache
import ofscraper.utils.config as config_

def separate_by_id(data: list, media_ids: list) -> list:
    media_ids=set(media_ids)
    return list(filter(lambda x:x.id not in media_ids,data ))


def seperate_avatars(data):
    return list(filter(lambda x:seperate_avatar_helper(x)==False,data))

def seperate_avatar_helper(ele):
    cache = Cache(getcachepath(),disk=config_.get_cache_mode(config_.read_config()))
    #id for avatar comes from xxh32 of url
    if  ele.postid and ele.responsetype_=="profile":
        value=cache.get(ele.postid ,False)
        cache.close()
        return value
    return False

    
  


# def separate_database_results_by_id(results: list, media_ids: list) -> list:
#     filtered_results = [r for r in results if r[0] not in media_ids]
#     return filtered_results
