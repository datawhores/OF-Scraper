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

dateNow = None
dateDict = None


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


def setLogDateVManager(dateDict_=None):
    global dateDict
    if dateDict_:
        dateDict = dateDict_
    elif not getLogDate():
        setDateNow()
        dateDict = {
            "day": dateNow.format("YYYY-MM-DD"),
            "now": dateNow.format("YYYY-MM-DD_HH.mm.ss"),
        }
    setLogDate(dateDict)
    manager.update_dict(dateDict)


def getLogDate():
    global dateDict
    return dateDict


def setLogDate(dateDict_=None):
    global dateDict
    if dateDict_:
        dateDict = dateDict_
    elif not getLogDate():
        setDateNow()
        dateDict = {
            "day": dateNow.format("YYYY-MM-DD"),
            "now": dateNow.format("YYYY-MM-DD_HH.mm.ss"),
        }


def getLogDateVManager():
    return dateDict


def resetLogDateVManager():
    global dateDict
    dateDict = None
    setLogDateVManager()


def resetLogDate():
    global dateDict
    dateDict = None
    setLogDate()


def format_seconds(total_seconds):
    """
    Formats a given time in seconds to "dd:hh:mm:ss" format.

    Args:
        total_seconds: The total number of seconds to be formatted.

    Returns:
        A string representing the formatted time in "dd:hh:mm:ss" format.
    """
    # Calculate days
    days = total_seconds // 86400
    # Remaining seconds after days
    remaining_seconds = total_seconds % 86400
    # Calculate hours
    hours = remaining_seconds // 3600
    # Remaining seconds after hours
    remaining_seconds = remaining_seconds % 3600
    # Calculate minutes
    minutes = remaining_seconds // 60
    # Remaining seconds
    seconds = remaining_seconds % 60
    # Format the output string
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"
