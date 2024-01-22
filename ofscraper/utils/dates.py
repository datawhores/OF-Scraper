r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

from datetime import datetime

import arrow

import ofscraper.utils.manager as manager

dateFormat = None
dateNow = None


def setDateNow():
    global dateNow
    dateNow = arrow.now()


def getDateNow():
    global dateNow
    if not dateNow:
        setDateNow()
    return dateNow


def convert_date_to_mdyhms(date: str):
    datetime_obj = datetime.fromisoformat(date)
    return datetime_obj.strftime("%B %d, %Y %I:%M:%S %p")


def convert_date_to_mdy(date: str):
    datetime_obj = datetime.fromisoformat(date)
    return datetime_obj.strftime("%B %d, %Y")


def convert_date_to_timestamp(date: str):
    datetime_obj = datetime.fromisoformat(date)
    return datetime_obj.timestamp()


def convert_local_time(date: str):
    return arrow.get(date, tzinfo="UTC").to("local").float_timestamp


def get_current_time():
    return arrow.get(tzinfo="UTC").to("local").float_timestamp


def setLogDate(dateDict=None):
    global dateFormat
    if not dateDict:
        global dateNow
        setDateNow()
        dateDict = {
            "day": dateNow.format("YYYY-MM-DD"),
            "now": dateNow.format("YYYY-MM-DD_hh.mm.ss"),
        }
    dateFormat = manager.get_manager().dict(dateDict)


def getLogDate():
    global dateFormat
    if not dateFormat:
        setLogDate()
    return dateFormat


def resetLogdate():
    global dateFormat
    dateFormat = None
    setLogDate()
