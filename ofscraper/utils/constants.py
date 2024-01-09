# trunk-ignore-all(black)
import importlib

from ofscraper.constants import *
from test_.test_constants import *

custom=None

def getattr(val):
    global custom
    #can not be overwritten cause of infinite loop
    if  val in { "configPath","configFile"}:
        return globals()[val]
    if custom ==None:
        config_=importlib.import_module("ofscraper.utils.config")
        custom=(config_.get_custom(config_.read_config(update=False)))
    return (custom or {}).get(val) or globals()[val]

