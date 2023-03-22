from time import sleep
from datetime import datetime,timedelta

last_long_sleep = datetime.now()
last_short_sleep = datetime.now()
def calculate_sleep():
    if datetime.now() - last_long_sleep >= timedelta(hours=16):
        return 28800
    return 7200



def nap_or_sleep():
    s = calculate_sleep()
    print(f"Sleeping for {s/60} minutes.")
    return s