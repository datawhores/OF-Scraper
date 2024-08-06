import logging

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.cache.read import read_full_after_scan_check


def get_after_pre_checks(model_id, api, forced_after=None):
    val = None
    if forced_after is not None:
        val = forced_after
    elif read_args.retriveArgs().after is not None:
        val = read_args.retriveArgs().after.float_timestamp
    elif not settings.auto_after_enabled():
        val = 0
    elif read_full_after_scan_check(model_id, api):
        val = 0
    return _return_val(val, api)


def _return_val(val, api):
    if val is None:
        logging.getLogger("shared").info(f"precheck failed for {api} using db")
        return val
    else:
        logging.getLogger("shared").info(f"precheck success for {api} skipping db")
        return val
