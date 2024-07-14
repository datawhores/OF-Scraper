import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants


def set_after_checks(model_id, api):
    api = api.lower()
    set_full_after_scan_check(model_id, api)


def set_full_after_scan_check(model_id, api):
    api = api.lower()
    cache.set(
        f"{model_id}_full_{api}_scrape", read_args.retriveArgs().after is not None
    )


def set_check_mode_posts(model_id, api, all_posts):
    api = api.lower()
    cache.set(
        f"{api}_check_{model_id}",
        list(all_posts),
        expire=constants.getattr("THREE_DAY_SECONDS"),
    )
