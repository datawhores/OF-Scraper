import os

import ofscraper.utils.config.custom as custom_
from ofscraper.const.constants import *
from ofscraper.const.values.test.test_constants import *

custom = None


def getattr(val):
    global custom
    # can not be overwritten cause of infinite loop
    if custom is None:
        try:
            custom = custom_.get_custom()
        except Exception as E:
            print(E)
            raise E
    return (
        os.environ.get(val) or (custom or {}).get(val)
        if (custom or {}).get(val) is not None
        else globals()[val]
    )


def setattr(key, val):
    global custom
    # can not be overwritten cause of infinite loop
    if custom is None:
        try:
            custom = custom_.get_custom()
        except Exception as E:
            print(E)
            raise E
    custom = custom or {}
    custom[key] = val
