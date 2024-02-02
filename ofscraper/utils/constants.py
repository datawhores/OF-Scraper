# trunk-ignore-all(black)
import ofscraper.utils.config.custom as custom_
from ofscraper.const.constants import *
from ofscraper.const.test_constants import *

custom=None

def getattr(val):
    global custom
    #can not be overwritten cause of infinite loop
    if custom ==None:
        try:
            custom=custom_.get_custom()
        except Exception as E:
            print(E)
            raise E
    return (custom or {}).get(val) or globals()[val]

