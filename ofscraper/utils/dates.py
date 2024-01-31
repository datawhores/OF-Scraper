r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

from datetime import datetime

import arrow

import ofscraper.utils.manager as manager

dateFormat = None
dateNow = None
dateDict=None


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


def setLogDateVManger(dateDict_=None):
    global dateFormat
    global dateDict
    dateDict=dateDict_
    if not dateDict:
        global dateNow
        setDateNow()
        dateDict = {
            "day": dateNow.format("YYYY-MM-DD"),
            "now": dateNow.format("YYYY-MM-DD_hh.mm.ss"),
        }
    dateFormat = manager.update_dict(dateDict)

def getDateDict():
    global dateDict
    return dateDict

def setDateDict(dateDict_):
    global dateDict
    dateDict=dateDict_


def getLogDateVManager():
    global dateFormat
    if not dateFormat:
        setLogDateVManger()
    return dateFormat


def resetLogDateVManger():
    global dateFormat
    dateFormat = None
    setLogDateVManger()
