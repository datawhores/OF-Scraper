# trunk-ignore-all(black)
import importlib

from ofscraper.constants import *
from test_.test_constants import *

custom=None

def getattr(val):
    global custom
    if custom==None:
        config_=importlib.import_module("ofscraper.utils.config")
        custom=(config_.get_custom(config_.read_config()))
    return (custom or {}).get(val) or globals()[val]

