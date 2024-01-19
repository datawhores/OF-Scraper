# trunk-ignore-all(black)
import ofscraper.utils.config.custom as custom_
from ofscraper.const.constants import *
from ofscraper.const.test_constants import *

custom=None

def getattr(val):
    global custom
    #can not be overwritten cause of infinite loop
    if  val in { "configPath","configFile"}:
        return globals()[val]
    if custom ==None:
        custom=custom_.get_custom()
    return (custom or {}).get(val) or globals()[val]

