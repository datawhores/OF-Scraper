
import logging
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.settings as settings
from ofscraper.api.common.cache.read import read_full_after_scan_check

def get_after_pre_checks(model_id,api, forced_after=None):
    if forced_after is not None:
        return forced_after
    elif read_args.retriveArgs().after != None:
        return read_args.retriveArgs().after.float_timestamp
    elif not settings.auto_after_enabled():
        return 0
    elif read_full_after_scan_check(model_id,api):
        return 
    logging.getLogger("shared").info(f"precheck failed for {api} using db")
    return None