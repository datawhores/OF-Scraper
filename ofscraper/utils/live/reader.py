
import ofscraper.utils.live.progress as progress_utils
def get_multi_download_curr_jobs_speed():
    return sum([ele.speed or  0 for ele in progress_utils.multi_download_job_progress.tasks])