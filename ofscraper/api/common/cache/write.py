import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
def set_after_checks(model_id,api):
    api=api.lower()
    set_full_after_scan_check(model_id,api)

def set_full_after_scan_check(model_id,api):
    api=api.lower()
    cache.set(
            f"{model_id}_full_{api}_scrape",
            read_args.retriveArgs().after is not None
    )


