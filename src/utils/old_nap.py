# from datetime import datetime, timedelta, date
# from random import randint, choice
# from time import sleep
#from rich.console import Console
console=Console()
#
# #CONFIG SLEEP
#
# max_hours_for_long_sleep = 12
# min_hours_for_long_sleep = 6
# max_seconds_for_short_sleep = 7200
# min_seconds_for_short_sleep = 1500
# work_start = 9
# work_end = 17
# max_minutes_for_variance = 20
# min_minutes_for_variance = 1
# human_sleep_hours_daily = 8
#
#
#
#
#
# #DO NOT EDIT BELOW THIS LINE
# last_scrape_finished_at = datetime.now() - timedelta(days=1)
# next_scrape_at = datetime.now() - timedelta(days=1)
# last_short_sleep_at = datetime.now() - timedelta(days=1)
# last_long_sleep_at = datetime.now() - timedelta(days=1)
#
# def workday():
#     today = date.today()
#     if today.weekday() < 5:
#         return True
#     else:
#         return False
#
# def is_workhours():
#     now = datetime.now()
#     if now.hour >= work_start and now.hour <= work_end:
#         return True
#     else:
#         return False
#
# def at_work():
#     if workday() and is_workhours():
#         return True
#     else:
#         return False
#
# def travel_time():
#     return randint(1170, 3900)
#
# def traveling():
#     with datetime.now() as now:
#         if now < now + timedelta(seconds=travel_time()) and now + timedelta(seconds=travel_time())  < datetime.replace(hour=work_start):
#             return False
#         else:
#             return True
#
# def at_home():
#     if not at_work() and not traveling():
#         return True
#     else:
#         return False
#
# def calculate_variance(t):
#     global max_minutes_for_variance, min_minutes_for_variance
#     variance = randint(min_minutes_for_variance, max_minutes_for_variance)
#     v = ['early', 'late']
#     if choice(v) == 'early':
#         return t - timedelta(minutes=variance)
#
#     else:
#         return t + timedelta(minutes=variance)
#
# def sleep_type():
#     global last_long_sleep_at, last_short_sleep_at
#     with datetime.now() as now:
#         if now - last_long_sleep_at > 24 - human_sleep_hours_daily:
#             return "long"
#         else:
#             return "short"
#
# def calculate_sleep():
#     global next_scrape_at
#     with datetime.now() as now:
#         if sleep_type() == "long":
#             sleep_time = calculate_variance(randint(min_hours_for_long_sleep, max_hours_for_long_sleep))
#             next_scrape_at = calculate_variance(now + timedelta(hours=sleep_time))
#             console.print(f"Sleeping for {sleep_time} hours")
#             console.print(f"Next scrape at {next_scrape_at}")
#             return sleep_time * 3600
#         else:
#             sleep_time = calculate_variance(randint(min_seconds_for_short_sleep, max_seconds_for_short_sleep))
#             next_scrape_at = calculate_variance(now + timedelta(seconds=sleep_time))
#             console.print(f"Sleeping for {sleep_time/60} minutes")
#             console.print(f"Next scrape at {next_scrape_at}")
#             return sleep_time

# This is the main function that is called to put the scraper to sleep.
# def nap_or_sleep():
#     sleep(calculate_sleep())