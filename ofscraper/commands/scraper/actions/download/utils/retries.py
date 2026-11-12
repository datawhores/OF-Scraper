import asyncio
import logging
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random

import ofscraper.utils.of_env.of_env as of_env
from ofscraper.commands.scraper.actions.utils.retries import get_download_retries
from ofscraper.managers.sessionmanager.sessionmanager import is_signed_cdn_forbidden


class NoRetry(Exception):
    """A download failure that retrying in this run won't fix. The item isn't
    marked as downloaded, so the next run tries again."""


class download_retry(AsyncRetrying):
    def __init__(self, stop=None, wait=None, retry=None) -> None:
        stop = stop or stop_after_attempt(get_download_retries())
        wait = wait or wait_random(
            min=of_env.getattr("OF_MIN_WAIT_API"),
            max=of_env.getattr("OF_MAX_WAIT_API"),
        )
        # a cancel (Ctrl+C, a cancelled task) stops the download: tenacity's
        # attempt swallows it, so it must not count as a failure
        retry = retry or retry_if_exception(
            lambda e: str(e) != of_env.getattr("SPACE_DOWNLOAD_MESSAGE")
            and not isinstance(e, (KeyboardInterrupt, asyncio.CancelledError, NoRetry))
            and not is_signed_cdn_forbidden(e)
        )
        
        def _log_retry(retry_state):
            logging.getLogger("shared").debug(
                f"Download interrupted/failed. Retrying in {retry_state.next_action.sleep:.2f}s "
                f"(Attempt {retry_state.attempt_number})"
            )

        super().__init__(
            stop=stop, 
            wait=wait, 
            retry=retry, 
            reraise=True,
            before_sleep=_log_retry
        )
