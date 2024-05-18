from ofscraper.utils.live.progress import activity_counter,activity_progress

activity_task=activity_progress.add_task(
            description='Running OF-Scraper'
     )
activity_counter_task=activity_counter.add_task(
            description='Overall script progress',
)
user_first_task=activity_counter.add_task(
            "",visible=False
)