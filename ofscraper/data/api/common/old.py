import logging
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.logs.logs import trace_log_raw

log = logging.getLogger("shared")

async def get_old_posts(model_id, username, db_function, api_name):
    """
    Universal function to retrieve and deduplicate old posts from the database.
    """
    # 1. Fetch from the database if the cache isn't disabled
    if not settings.get_settings().api_cached_disabled:
        old_data = await db_function(model_id=model_id, username=username)
    else:
        old_data = []
        
    # Filter out None values just in case
    old_data = list(filter(lambda x: x is not None, old_data))
    
    # 2. Deduplicate based on post_id
    seen = set()
    old_data = [
        post
        for post in old_data
        if post["post_id"] not in seen and not seen.add(post["post_id"])
    ]
    
    # 3. Log the results
    log.debug(f"[bold]{api_name} Cache[/bold] {len(old_data)} found")
    trace_log_raw(f"old{api_name.lower()}", old_data)
    
    return old_data