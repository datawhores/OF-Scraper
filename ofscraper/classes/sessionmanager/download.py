import contextlib
import time
import asyncio
import ofscraper.classes.sessionmanager.ofsession as ofsessionmanager
import ofscraper.classes.sessionmanager.sessionmanager as sessionManager
import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.constants as constants
from ofscraper.actions.utils.retries import get_download_req_retries
from ofscraper.classes.sessionmanager.sessionmanager import (
    AUTH,
    COOKIES,
    FORCED_NEW,
    HEADERS,
    SIGN,
    TOO_MANY,
)
from ofscraper.classes.sessionmanager.leaky import LeakyBucket
import ofscraper.utils.settings as settings


class TokenBucket:
    def __init__(self, capacity, fill_rate):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = 0
        self.last_update = time.time()

    async def consume(self, tokens):
        if self.capacity <= 0:
            return True
        while True:
            now = time.time()
            delta = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + delta * self.fill_rate)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            # Not enough tokens, wait for refill
            await asyncio.sleep(0.01)


class download_session(sessionManager.sessionManager):
    def __init__(
        self, sem_count=None, retries=None, wait_min=None, wait_max=None, log=None
    ) -> None:
        sem_count = sem_count or common_globals.sem
        retries = retries or get_download_req_retries()
        wait_min = wait_min or constants.getattr("OF_MIN_WAIT_API")
        wait_max = wait_max or constants.getattr("OF_MAX_WAIT_API")
        log = log or common_globals.log
        self.leaky_bucket = LeakyBucket(settings.get_download_limit(), 1)
        super().__init__(
            sem_count=sem_count,
            retries=retries,
            wait_min=wait_min,
            wait_max=wait_max,
            log=log,
        )

    @contextlib.asynccontextmanager
    async def requests_async(self, *args, **kwargs):
        if not kwargs.get("actions"):
            actions = [SIGN, COOKIES, HEADERS]
            actions.append([FORCED_NEW]) if constants.getattr("API_FORCE_KEY") else None
            kwargs["actions"] = actions
        kwargs["exceptions"] = [TOO_MANY, AUTH]
        async with super().requests_async(*args, **kwargs) as r:
            yield r

    async def _httpx_funct_async(self, *args, **kwargs):
        t = await self._session.request(*args, **kwargs)
        t.ok = not t.is_error
        t.json_ = lambda: self.factoryasync(t.json)
        t.text_ = lambda: self.factoryasync(t.text)
        t.status = t.status_code
        t.iter_chunked = self.chunk_with_limit(t.aiter_bytes)
        t.iter_chunks = self.chunk_with_limit(t.aiter_bytes)
        t.read_ = t.aread
        t.request = t.request
        return t

    async def _aio_funct(self, method, *args, **kwargs):
        # public function forces context manager use
        r = await self._session._request(method, *args, **kwargs)
        r.text_ = r.text
        r.json_ = r.json
        r.iter_chunked = self.chunk_with_limit(r.content.iter_chunked)
        r.iter_chunks = self.chunk_with_limit(r.content.iter_chunks)
        r.request = r.request_info
        r.status_code = r.status
        r.read_ = r.content.read
        r.eof = r.content.at_eof
        return r

    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input

    def chunk_with_limit(self, funct):
        async def wrapper(*args, **kwargs):
            async for chunk in funct(*args, **kwargs):
                size = len(chunk)
                await self.get_token(size)
                yield chunk
        return wrapper

    async def get_token(self, size):
        await self.leaky_bucket.acquire(size)


class cdm_session(sessionManager.sessionManager):
    def __init__(self, backend=None, sem_count=None) -> None:
        backend = backend or "httpx"
        sem_count = sem_count or common_globals.sem
        super().__init__(sem_count=sem_count, backend=backend)


class cdm_session_manual(ofsessionmanager.OFSessionManager):
    def __init__(self, backend=None, sem_count=None) -> None:
        backend = backend or "httpx"
        sem_count = sem_count or common_globals.sem
        super().__init__(sem_count=sem_count, backend=backend)
