import ofscraper.utils.cache as cache
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


def set_check_mode_posts(model_id, api, all_posts):
    api = api.lower()
    cache.set(
        f"{api}_v2_check_{model_id}",
        list(all_posts),
        expire=of_env.getattr("THREE_DAY_SECONDS"),
    )
