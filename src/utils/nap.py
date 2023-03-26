from time import sleep
from datetime import datetime,timedelta
from rich.console import Console
console=Console()

last_long_sleep = datetime.now()
last_short_sleep = datetime.now()
def calculate_sleep():
    if datetime.now() - last_long_sleep >= timedelta(hours=16):
        return 28800
    return 7200



def nap_or_sleep():
    s = calculate_sleep()
    console.print(f"Sleeping for {s/60} minutes.")
    return s