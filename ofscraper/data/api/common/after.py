import logging

import ofscraper.utils.settings as settings
from ofscraper.data.api.common.cache.read import read_full_after_scan_check


def get_after_pre_checks(model_id, api):
    val = None
    if settings.get_settings().after == 0:
        val = 0
    elif settings.get_settings().after is not None:
        val = settings.get_settings().after.float_timestamp
    elif not settings.get_settings().auto_after:
        val = 0
    elif read_full_after_scan_check(model_id, api):
        val = 0
    elif "like" in settings.get_settings().action:
        val = 0
    elif "unlike" in settings.get_settings().action:
        val = 0
    return _return_val(val, api)


def _return_val(val, api):
    if val is None:
        logging.getLogger("shared").info(
            f"precheck failed for setting after {api} using db"
        )
        return val
    else:
        logging.getLogger("shared").info(
            f"precheck success for setting after {api} skipping db"
        )
        return val
