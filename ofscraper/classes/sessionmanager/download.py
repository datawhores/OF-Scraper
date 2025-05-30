import contextlib
import ofscraper.classes.sessionmanager.ofsession as ofsessionmanager
import ofscraper.classes.sessionmanager.sessionmanager as sessionManager
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.constants as constants
from ofscraper.commands.scraper.actions.utils.retries import get_download_req_retries
from ofscraper.classes.sessionmanager.sessionmanager import (
    AUTH,
    COOKIES,
    FORCED_NEW,
    HEADERS,
    SIGN,
    TOO_MANY,
)
from ofscraper.commands.scraper.actions.download.utils.leaky import LeakyBucket
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download.utils.chunk import get_chunk_timeout


class download_session(sessionManager.sessionManager):
    def __init__(
        self, sem_count=None, retries=None, wait_min=None, wait_max=None, log=None
    ) -> None:
        retries = retries or get_download_req_retries()
        wait_min = wait_min or constants.getattr("OF_MIN_WAIT_API")
        wait_max = wait_max or constants.getattr("OF_MAX_WAIT_API")
        read_timeout=get_chunk_timeout()
        log = log or common_globals.log
        self.leaky_bucket = LeakyBucket(settings.get_settings().download_limit, 1)




        super().__init__(
            sem_count=sem_count,
            retries=retries,
            wait_min=wait_min,
            wait_max=wait_max,
            log=log,
            read_timeout=read_timeout
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

    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input

    def chunk_with_limit(self, funct):
        async def wrapper(*args, **kwargs):
            async for chunk in funct(*args, **kwargs):
                await self.get_token(chunk)
                yield chunk

        return wrapper

    async def get_token(self, chunk):
        await self.leaky_bucket.acquire(chunk)


class cdm_session(sessionManager.sessionManager):
    def __init__(self,  sem_count=None) -> None:
        super().__init__(sem_count=sem_count)


class cdm_session_manual(ofsessionmanager.OFSessionManager):
    def __init__(self,  sem_count=None) -> None:
        super().__init__(sem_count=sem_count)
