import asyncio
from functools import partial
import ofscraper.utils.cache.cache as cache


def get_profile_cache_key(ele):
    """
    Standardizes the key format to namespace by username.
    Uses the xxh32 hash stored in post_id for Profiles.
    """
    return f"avatar_{ele.username}_{ele.post_id}"


async def set_profile_cache(ele, thread_executor):
    """
    The hardened writer: Marks an avatar/header as downloaded.
    """
    if ele.post_id and ele.responsetype.capitalize() == "Profile":
        key = get_profile_cache_key(ele)
        await asyncio.get_event_loop().run_in_executor(
            thread_executor, partial(cache.set, key, True)
        )


def is_profile_cached(ele):
    """
    The hardened reader: Checks if an avatar/header exists in cache.
    """
    if ele.post_id and ele.responsetype.capitalize() == "Profile":
        key = get_profile_cache_key(ele)
        return cache.get(key, default=False)
    return False
