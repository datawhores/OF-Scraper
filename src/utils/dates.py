r"""
               _          __                                                                      
  ___   _ __  | | _   _  / _|  __ _  _ __   ___         ___   ___  _ __   __ _  _ __    ___  _ __ 
 / _ \ | '_ \ | || | | || |_  / _` || '_ \ / __| _____ / __| / __|| '__| / _` || '_ \  / _ \| '__|
| (_) || | | || || |_| ||  _|| (_| || | | |\__ \|_____|\__ \| (__ | |   | (_| || |_) ||  __/| |   
 \___/ |_| |_||_| \__, ||_|   \__,_||_| |_||___/       |___/ \___||_|    \__,_|| .__/  \___||_|   
                  |___/                                                        |_|                
"""

from datetime import datetime


def convert_date_to_mdyhms(date: str):
    datetime_obj = datetime.fromisoformat(date)
    return datetime_obj.strftime('%B %d, %Y %I:%M:%S %p')


def convert_date_to_mdy(date: str):
    datetime_obj = datetime.fromisoformat(date)
    return datetime_obj.strftime('%B %d, %Y')


def convert_date_to_timestamp(date: str):
    datetime_obj = datetime.fromisoformat(date)
    return datetime_obj.timestamp()
