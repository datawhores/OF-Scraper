# trunk-ignore-all(black)
import sys

import ofscraper.utils.config as config_
from ofscraper.constants import *
from test_.test_constants import *

config=None
thismodule = sys.modules[__name__]


def getattr(val):
    global config
    if config==None:
        config=config_.read_config()
    return (config_.get_custom(config) or {}).get(val) or globals()[val]

