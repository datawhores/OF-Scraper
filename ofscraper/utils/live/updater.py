from ofscraper.utils.live.progress import download_job_progress,download_overall_progress,multi_download_job_progress,live,activity_counter,activity_progress


from ofscraper.utils.live.tasks import activity_counter_task,activity_task,user_first_task
def update_activity_task(**kwargs):
    activity_progress.update(
           activity_task, **kwargs
    )

def increment_activity_count():
    activity_counter_task
    activity_counter.update(
           activity_counter_task,advance=1
    )


def update_activity_count(**kwargs):
    activity_counter.update(
           activity_counter_task,**kwargs
    )



def add_user_first_activity(**kwargs):
    activity_counter.update(
            user_first_task,**kwargs
    )

def increment_user_first_activity():
    activity_counter.update(
           user_first_task,advance=1
    )

def update_first_activity(**kwargs):
    activity_counter.update(
          user_first_task,  **kwargs
    )