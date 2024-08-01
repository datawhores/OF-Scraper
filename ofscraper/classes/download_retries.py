from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random

import ofscraper.utils.constants as constants
from ofscraper.actions.utils.retries import get_download_retries


class download_retry(AsyncRetrying):
    def __init__(self, stop=None, wait=None, retry=None) -> None:
        stop = stop or stop_after_attempt(get_download_retries())
        wait = wait or wait_random(
            min=constants.getattr("OF_MIN_WAIT_API"),
            max=constants.getattr("OF_MAX_WAIT_API"),
        )
        retry = retry or retry_if_exception(
            lambda e: str(e) != constants.getattr("SPACE_DOWNLOAD_MESSAGE")
            and not isinstance(e, KeyboardInterrupt)
        )
        super().__init__(stop=stop, wait=wait, retry=retry, reraise=True)
