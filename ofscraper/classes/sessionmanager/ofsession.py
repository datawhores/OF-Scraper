import contextlib
import logging
import asyncio
import threading
from typing import Optional, Dict, List, Any, AsyncGenerator, Generator

import ofscraper.utils.of_env.of_env as of_env
from ofscraper.classes.sessionmanager.sessionmanager import (
    AUTH,
    COOKIES,
    FORCED_NEW,
    FORBIDDEN,
    HEADERS,
    SIGN,
    TOO_MANY,
    sessionManager,
)

# Imports for the new session classes
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.utils.retries import get_download_req_retries
from ofscraper.commands.scraper.actions.download.utils.leaky import LeakyBucket
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download.utils.chunk import get_chunk_timeout
from ofscraper.classes.sessionmanager.sleepers import (
    rate_limit_session_sleeper,
    forbidden_session_sleeper,
    download_forbidden_session_sleeper,
    download_rate_limit_session_sleeper,
)
from ofscraper.classes.sessionmanager.sleepers import (
    cdm_rate_limit_session_sleeper,
    cdm_forbidden_session_sleeper,
    like_rate_limit_session_sleeper,
    like_forbidden_session_sleeper,
)


class OFSessionManager(sessionManager):
    """
    A specialized sessionManager for OF API interactions, with preset
    actions, exceptions, and specific default values for retries and limits.
    """

    def __init__(
        self,
        # --- Standard sessionManager parameters ---
        connect_timeout: Optional[int] = None,
        total_timeout: Optional[int] = None,
        read_timeout: Optional[int] = None,
        pool_timeout: Optional[int] = None,
        limit: Optional[int] = None,
        keep_alive: Optional[int] = None,
        keep_alive_exp: Optional[int] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[Dict] = None,
        delay: Optional[float] = None,
        sem_count: Optional[int] = None,
        retries: Optional[int] = None,
        wait_min: Optional[int] = None,
        wait_max: Optional[int] = None,
        wait_min_exponential: Optional[int] = None,
        wait_max_exponential: Optional[int] = None,
        log: Optional[logging.Logger] = None,
        sem: Optional[asyncio.Semaphore] = None,
        sync_sem_count: Optional[int] = None,
        sync_sem: Optional[threading.Semaphore] = None,
        # ---rate limit sleepers
        rate_limit_sleeper: Optional[float] = rate_limit_session_sleeper,
        forbidden_sleeper: Optional[float] = forbidden_session_sleeper,
    ):
        # --- Apply specialized defaults for this subclass ---
        limit = limit if limit is not None else of_env.getattr("API_MAX_CONNECTION")
        # Assuming API_INDVIDIUAL_NUM_TRIES is a valid key in your config
        retries = (
            retries
            if retries is not None
            else of_env.getattr("API_INDVIDIUAL_NUM_TRIES")
        )
        wait_min = (
            wait_min if wait_min is not None else of_env.getattr("OF_MIN_WAIT_API")
        )
        wait_max = (
            wait_max if wait_max is not None else of_env.getattr("OF_MAX_WAIT_API")
        )

        super().__init__(
            connect_timeout=connect_timeout,
            total_timeout=total_timeout,
            read_timeout=read_timeout,
            pool_timeout=pool_timeout,
            limit=limit,
            keep_alive=keep_alive,
            keep_alive_exp=keep_alive_exp,
            proxy=proxy,
            proxy_auth=proxy_auth,
            sem_count=sem_count,
            retries=retries,
            wait_min=wait_min,
            wait_max=wait_max,
            wait_min_exponential=wait_min_exponential,
            wait_max_exponential=wait_max_exponential,
            log=log,
            sem=sem,
            sync_sem_count=sync_sem_count,
            sync_sem=sync_sem,
            rate_limit_sleeper=rate_limit_sleeper,
            forbidden_sleeper=forbidden_sleeper,
        )

    @contextlib.asynccontextmanager
    async def requests_async(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """A wrapper for async requests with preset actions and exceptions."""
        actions: List[str] = [SIGN, COOKIES, HEADERS]
        # Add FORBIDDEN to the default exceptions for this specific session type
        exceptions: List[str] = [TOO_MANY, AUTH, FORBIDDEN]
        if of_env.getattr("API_FORCE_KEY"):
            actions.append(FORCED_NEW)

        # Allow kwargs to override the defaults
        kwargs["actions"] = kwargs.get("actions", actions)
        kwargs["exceptions"] = kwargs.get("exceptions", exceptions)

        async with super().requests_async(*args, **kwargs) as r:
            yield r

    @contextlib.contextmanager
    def requests(self, *args: Any, **kwargs: Any) -> Generator[Any, None, None]:
        """A wrapper for sync requests with preset actions and exceptions."""
        actions: List[str] = [SIGN, COOKIES, HEADERS]
        # Add FORBIDDEN to the default exceptions for this specific session type
        exceptions: List[str] = [TOO_MANY, AUTH, FORBIDDEN]
        if of_env.getattr("API_FORCE_KEY"):
            actions.append(FORCED_NEW)

        # Allow kwargs to override the defaults
        kwargs["actions"] = kwargs.get("actions", actions)
        kwargs["exceptions"] = kwargs.get("exceptions", exceptions)

        with super().requests(*args, **kwargs) as r:
            yield r


class download_session(sessionManager):
    """
    A specialized sessionManager for file downloads, with a leaky bucket for speed limiting
    and specific retry/timeout settings.
    """

    def __init__(
        self,
        sem_count=None,
        # ---rate limit sleepers
        rate_limit_sleeper: Optional[float] = download_rate_limit_session_sleeper,
        forbidden_sleeper: Optional[float] = download_forbidden_session_sleeper,
        **kwargs: Any,
    ) -> None:
        # --- Apply specialized defaults for download sessions ---
        retries = kwargs.pop("retries", None) or get_download_req_retries()
        wait_min = kwargs.pop("wait_min", None) or of_env.getattr("OF_MIN_WAIT_API")
        wait_max = kwargs.pop("wait_max", None) or of_env.getattr("OF_MAX_WAIT_API")
        read_timeout = kwargs.pop("read_timeout", None) or get_chunk_timeout()
        log = kwargs.pop("log", None) or common_globals.log
        self.leaky_bucket = LeakyBucket(settings.get_settings().download_limit, 1)

        super().__init__(
            sem_count=sem_count,
            retries=retries,
            wait_min=wait_min,
            wait_max=wait_max,
            log=log,
            read_timeout=read_timeout,
            **kwargs,
        )

    @contextlib.asynccontextmanager
    async def requests_async(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        # Set default actions and exceptions for downloads
        if not kwargs.get("actions"):
            actions = [SIGN, COOKIES, HEADERS]
            if of_env.getattr("API_FORCE_KEY"):
                actions.append(FORCED_NEW)
            kwargs["actions"] = actions
        kwargs["exceptions"] = [TOO_MANY, AUTH]

        async with super().requests_async(*args, **kwargs) as r:
            yield r

    async def _httpx_funct_async(self, *args, **kwargs):
        """Wraps the parent method to add download speed limiting to chunk iteration."""
        t = await super()._httpx_funct_async(*args, **kwargs)

        # Override chunk iterators to use the leaky bucket
        t.iter_chunked = self.chunk_with_limit(t.iter_chunked)
        t.iter_chunks = self.chunk_with_limit(t.iter_chunks)
        return t

    def chunk_with_limit(self, funct):
        """Decorator to apply the leaky bucket to an async chunk generator."""

        async def wrapper(*args, **kwargs):
            async for chunk in funct(*args, **kwargs):
                await self.get_token(len(chunk))
                yield chunk

        return wrapper

    async def get_token(self, size: int):
        """Acquires tokens from the leaky bucket corresponding to the chunk size."""
        await self.leaky_bucket.acquire(size)


class cdm_session(sessionManager):
    """A session manager for CDM operations."""

    def __init__(self, sem_count: Optional[int] = None, **kwargs: Any) -> None:
        super().__init__(sem_count=sem_count, **kwargs)


class cdm_session_manual(OFSessionManager):
    """A session manager for manual CDM operations, using OFSessionManager presets."""

    def __init__(
        self,
        sem_count: Optional[int] = None,  # ---rate limit sleepers
        rate_limit_sleeper: Optional[float] = cdm_rate_limit_session_sleeper,
        forbidden_sleeper: Optional[float] = cdm_forbidden_session_sleeper,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sem_count=sem_count,
            rate_limit_sleeper=rate_limit_sleeper,
            forbidden_sleeper=forbidden_sleeper,**kwargs,
        )


class like_session(OFSessionManager):
    """A session manager for manual CDM operations, using OFSessionManager presets."""

    def __init__(
        self,
        sem_count: Optional[int] = None,  # ---rate limit sleepers
        rate_limit_sleeper: Optional[float] = like_rate_limit_session_sleeper,
        forbidden_sleeper: Optional[float] = like_forbidden_session_sleeper,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sem_count=sem_count,
            rate_limit_sleeper=rate_limit_sleeper,
            forbidden_sleeper=forbidden_sleeper,**kwargs,
        )
