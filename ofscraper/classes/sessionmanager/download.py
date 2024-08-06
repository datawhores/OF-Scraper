import contextlib
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


class download_session(sessionManager.sessionManager):
    def __init__(
        self, sem_count=None, retries=None, wait_min=None, wait_max=None, log=None
    ) -> None:
        sem_count = sem_count or common_globals.sem
        retries = retries or get_download_req_retries()
        wait_min = wait_min or constants.getattr("OF_MIN_WAIT_API")
        wait_max = wait_max or constants.getattr("OF_MAX_WAIT_API")
        log = log or common_globals.log
        self.lock=asyncio.Lock()
        self.token_bucket=1024*1024
        self.max_fill=1024*1024
        self.fill_task = asyncio.create_task(self._token_filler())
        super().__init__(
            sem_count=sem_count, retries=retries, wait_min=wait_min, wait_max=wait_max, log=log
        )
    @contextlib.asynccontextmanager
    async def requests_async(self, *args, **kwargs):
        if not kwargs.get("actions"):
            actions = [SIGN, COOKIES, HEADERS]
            actions.append([FORCED_NEW]) if constants.getattr("API_FORCE_KEY") else None
            kwargs["actions"]= actions
        kwargs["exceptions"]= [TOO_MANY, AUTH]
        async with super().requests_async(
            *args,**kwargs
        ) as r:
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
        r.eof=r.content.at_eof
        return r

    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input
    async def _token_filler(self):
        while True:
            while self.token_bucket<self.max_fill:
                async with self.lock:
                    self.token_bucket += (1024*1024) * 0.2
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)
    def chunk_with_limit(self, funct):
        async def wrapper(*args, **kwargs):
            size = args[0]
            async for chunk in funct(*args, **kwargs):
                yield chunk
                # while True:
                #     async with self.lock:
                #         if self.token_bucket >=size:
                #             self.token_bucket -= size
                #             yield chunk                    
        return wrapper
    


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
