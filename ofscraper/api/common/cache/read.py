import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache


def read_full_after_scan_check(model_id, api):
    api = api.lower()
    return cache.get(
        f"{model_id}_full_{api}_scrape",
        read_args.retriveArgs().after is not None,
    )


def read_one_good_scan_check(model_id, api):
    api = api.lower()
    return cache.get(f"{api}_one_good_scan_{model_id}")


def read_check_mode(model_id, api):
    api = api.lower()
    return cache.get(f"{api}_check_{model_id}", default=[])
