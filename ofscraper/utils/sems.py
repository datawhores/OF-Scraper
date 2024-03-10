sem = None
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed


def get_req_sem():
    global sem
    if not sem:
        sem = semaphoreDelayed(constants.getattr("MAX_SEMAPHORE"))
    return sem
