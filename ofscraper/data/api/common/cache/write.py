import arrow
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings


def set_after_checks(model_id, api):
    api = api.lower()
    set_full_after_scan_check(model_id, api)


def set_full_after_scan_check(model_id, api):
    api = api.lower()
    cache.set(
        f"{model_id}_full_{api}_v2_scrape", settings.get_settings().after is not None
    )


def set_check_mode_posts(model_id, api, all_posts, update=False):
    api = api.lower()
    key = f"{api}_v2_check_{model_id}"
    expire_key = f"{key}_expire_time"

    now = arrow.now().float_timestamp
    expire_time = cache.get(expire_key)
    
    # If it's a fresh/forced fetch (!update), or we lost the expiration time, reset the 3-day clock
    if not update or not expire_time or now > expire_time:
        remaining = of_env.getattr("THREE_DAY_SECONDS")
        expire_time = now + remaining
        cache.set(expire_key, expire_time, expire=remaining)
    else:
        # We are just appending new items, preserve the original expiration clock
        remaining = max(1, expire_time - now)

    cache.set(
        key,
        list(all_posts),
        expire=remaining,
    )