import contextlib

import ofscraper.utils.constants as constants
from ofscraper.classes.sessionmanager.sessionmanager import (
    AUTH,
    COOKIES,
    FORCED_NEW,
    HEADERS,
    SIGN,
    TOO_MANY,
    sessionManager,
)


class OFSessionManager(sessionManager):
    def __init__(
        self,
        backend=None,
        connect_timeout=None,
        total_timeout=None,
        read_timeout=None,
        pool_timeout=None,
        limit=None,
        keep_alive=None,
        keep_alive_exp=None,
        proxy=None,
        proxy_auth=None,
        delay=None,
        sem_count=None,
        retries=None,
        wait_min=None,
        wait_max=None,
        wait_min_exponential=None,
        wait_max_exponential=None,
        log=None,
        semaphore=None,
        sync_sem_count=None,
        sync_semaphore=None,
    ):
        limit = limit if limit is not None else constants.getattr("API_MAX_CONNECTION")
        retries = (
            retries
            if retries is not None
            else constants.getattr("API_INDVIDIUAL_NUM_TRIES")
        )
        wait_min = (
            wait_min if wait_min is not None else constants.getattr("OF_MIN_WAIT_API")
        )
        wait_max = (
            wait_max if wait_max is not None else constants.getattr("OF_MAX_WAIT_API")
        )
        super().__init__(
            backend,
            connect_timeout,
            total_timeout,
            read_timeout,
            pool_timeout,
            limit,
            keep_alive,
            keep_alive_exp,
            proxy,
            proxy_auth,
            delay,
            sem_count,
            retries,
            wait_min,
            wait_max,
            wait_min_exponential,
            wait_max_exponential,
            log,
            semaphore,
            sync_sem_count,
            sync_semaphore,
        )

    @contextlib.asynccontextmanager
    async def requests_async(self, *args, **kwargs):
        actions = [SIGN, COOKIES, HEADERS]
        exceptions = [TOO_MANY, AUTH]
        actions.append([FORCED_NEW]) if constants.getattr("API_FORCE_KEY") else None
        async with super().requests_async(
            *args, actions=actions, exceptions=exceptions, **kwargs
        ) as r:
            yield r

    @contextlib.contextmanager
    def requests(self, *args, **kwargs):
        actions = [SIGN, COOKIES, HEADERS]
        exceptions = [TOO_MANY, AUTH]
        actions.append([FORCED_NEW]) if constants.getattr("API_FORCE_KEY") else None
        with super().requests(
            *args, actions=actions, exceptions=exceptions, **kwargs
        ) as r:
            yield r
