import logging

import ofscraper.utils.args.accessors.read as read_args
from ofscraper.utils.args.accessors.actions import get_actions
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.cache.read import read_full_after_scan_check


def get_after_pre_checks(model_id, api):
    val = None
    if read_args.retriveArgs().after==0:
        val=0
    elif read_args.retriveArgs().after is not None:
        val = read_args.retriveArgs().after.float_timestamp
    elif not settings.auto_after_enabled():
        val = 0
    elif read_full_after_scan_check(model_id, api):
        val = 0
    elif "like" in get_actions():
        val =0
    elif "unlike" in get_actions():
        val =0
    return _return_val(val, api)


def _return_val(val, api):
    if val is None:
        logging.getLogger("shared").info(f"precheck failed for setting after {api} using db")
        return val
    else:
        logging.getLogger("shared").info(f"precheck success for setting after {api} skipping db")
        return val
