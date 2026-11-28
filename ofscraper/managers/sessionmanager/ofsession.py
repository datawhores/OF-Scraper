import asyncio
import contextlib
import logging
import threading
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional

# Imports for the new session classes
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download.utils.chunk import get_chunk_timeout
from ofscraper.commands.scraper.actions.download.utils.leaky import LeakyBucket
from ofscraper.commands.scraper.actions.utils.retries import get_download_req_retries
from ofscraper.managers.sessionmanager.sessionmanager import (
    AUTH,
    COOKIES,
    FORBIDDEN,
    FORCED_NEW,
    HEADERS,
    SIGN,
    TOO_MANY,
    sessionManager,
)
from ofscraper.managers.sessionmanager.sleepers import sleepers

_UNSET: Any = object()


def _resolve_sleepers(
    session: Any, rate_limit_sleeper: Any, forbidden_sleeper: Any
) -> tuple[Any, Any]:
    if rate_limit_sleeper is _UNSET:
        rate_limit_sleeper = getattr(sleepers, session.default_rate_limit_sleeper)
    if forbidden_sleeper is _UNSET:
        forbidden_sleeper = getattr(sleepers, session.default_forbidden_sleeper)
    return rate_limit_sleeper, forbidden_sleeper


def _default_actions() -> List[str]:
    actions: List[str] = [SIGN, COOKIES, HEADERS]
    if of_env.getattr("API_FORCE_KEY"):
        actions.append(FORCED_NEW)
    return actions


def _apply_default_request_kwargs(
    kwargs: Dict[str, Any],
    default_exceptions: List[str],
    *,
    treat_empty_actions_as_default: bool = False,
) -> None:
    if "actions" not in kwargs or (
        treat_empty_actions_as_default and not kwargs.get("actions")
    ):
        kwargs["actions"] = _default_actions()
    if "exceptions" not in kwargs:
        kwargs["exceptions"] = list(default_exceptions)


class OFSessionManager(sessionManager):
    """
    A specialized sessionManager for OF API interactions, with preset
    actions, exceptions, and specific default values for retries and limits.
    """

    default_rate_limit_sleeper: str = "rate_limit_session_sleeper"
    default_forbidden_sleeper: str = "forbidden_session_sleeper"

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
        log: Optional[logging.Logger] = None,
        sem: Optional[asyncio.Semaphore] = None,
        sync_sem_count: Optional[int] = None,
        sync_sem: Optional[threading.Semaphore] = None,
        # ---rate limit sleepers
        rate_limit_sleeper: Any = _UNSET,
        forbidden_sleeper: Any = _UNSET,
    ):
        rate_limit_sleeper, forbidden_sleeper = _resolve_sleepers(
            self, rate_limit_sleeper, forbidden_sleeper
        )
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
        _apply_default_request_kwargs(kwargs, [TOO_MANY, AUTH, FORBIDDEN])

        async with super().requests_async(*args, **kwargs) as r:
            yield r

    @contextlib.contextmanager
    def requests(self, *args: Any, **kwargs: Any) -> Generator[Any, None, None]:
        """A wrapper for sync requests with preset actions and exceptions."""
        _apply_default_request_kwargs(kwargs, [TOO_MANY, AUTH, FORBIDDEN])

        with super().requests(*args, **kwargs) as r:
            yield r


class download_session(sessionManager):
    """
    A specialized sessionManager for file downloads, with a leaky bucket for speed limiting
    and specific retry/timeout settings.
    """

    default_rate_limit_sleeper: str = "download_rate_limit_session_sleeper"
    default_forbidden_sleeper: str = "download_forbidden_session_sleeper"

    def __init__(
        self,
        sem_count=None,
        # ---rate limit sleepers
        rate_limit_sleeper: Any = _UNSET,
        forbidden_sleeper: Any = _UNSET,
        **kwargs: Any,
    ) -> None:
        rate_limit_sleeper, forbidden_sleeper = _resolve_sleepers(
            self, rate_limit_sleeper, forbidden_sleeper
        )
        # --- Apply specialized defaults for download sessions ---
        # only None means "use the default": 0 retries or a 0 s wait is a value
        retries = kwargs.pop("retries", None)
        if retries is None:
            retries = get_download_req_retries()
        wait_min = kwargs.pop("wait_min", None)
        if wait_min is None:
            wait_min = of_env.getattr("OF_MIN_WAIT_API")
        wait_max = kwargs.pop("wait_max", None)
        if wait_max is None:
            wait_max = of_env.getattr("OF_MAX_WAIT_API")
        read_timeout = kwargs.pop("read_timeout", None)
        if read_timeout is None:
            read_timeout = get_chunk_timeout()
        log = kwargs.pop("log", None) or common_globals.log
        self.leaky_bucket = LeakyBucket(settings.get_settings().download_limit, 1)

        super().__init__(
            sem_count=sem_count,
            retries=retries,
            wait_min=wait_min,
            wait_max=wait_max,
            log=log,
            read_timeout=read_timeout,
            rate_limit_sleeper=rate_limit_sleeper,
            forbidden_sleeper=forbidden_sleeper,
            **kwargs,
        )
        # A read timeout of 0 means no limit (None). aiohttp reads 0 that way,
        # but httpx reads 0 as "fail at once". Set here, after the base class:
        # a None passed to it means "use OF_READ_TIMEOUT".
        if self._read_timeout == 0:
            self._read_timeout = None

    @contextlib.asynccontextmanager
    async def requests_async(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        # Set default actions and exceptions for downloads; callers such as
        # metadata/manager.py pass actions=[] to ask for the default actions.
        _apply_default_request_kwargs(
            kwargs, [TOO_MANY, AUTH], treat_empty_actions_as_default=True
        )

        async with super().requests_async(*args, **kwargs) as r:
            yield r

    async def _aio_funct(self, *args, **kwargs):
        """Wraps the parent method to add download speed limiting to chunk iteration."""
        t = await super()._aio_funct(*args, **kwargs)

        # Override the chunk iterator to use the leaky bucket. iter_chunks is
        # left alone: it yields (data, end_of_chunk) tuples and nothing uses it.
        t.iter_chunked = self.chunk_with_limit(t.iter_chunked)
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


class metadata_session(download_session):
    """A specialized sessionManager for metadata operations."""

    default_rate_limit_sleeper = "metadata_rate_limit_session_sleeper"
    default_forbidden_sleeper = "metadata_forbidden_session_sleeper"


class cdm_session(sessionManager):
    """A session manager for CDM operations."""


class cdm_session_manual(OFSessionManager):
    """A session manager for manual CDM operations, using OFSessionManager presets."""

    default_rate_limit_sleeper = "cdm_rate_limit_session_sleeper"
    default_forbidden_sleeper = "cdm_forbidden_session_sleeper"


class like_session(OFSessionManager):
    """A session manager for like operations, using OFSessionManager presets."""

    default_rate_limit_sleeper = "like_rate_limit_session_sleeper"
    default_forbidden_sleeper = "like_forbidden_session_sleeper"


class SubscriptionSessionManager(OFSessionManager):
    """A session manager for subscription operations, using OFSessionManager presets."""

    default_rate_limit_sleeper = "subscription_rate_limit_session_sleeper"
    default_forbidden_sleeper = "subscription_forbidden_session_sleeper"
