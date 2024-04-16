import asyncio
import contextlib
import logging
import ssl
import threading
import traceback

import aiohttp
import certifi
import httpx
import tenacity
from tenacity import AsyncRetrying, Retrying, retry_if_not_exception_type

import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants


class CustomTenacity(AsyncRetrying):
    """
    A custom context manager using tenacity for asynchronous retries with wait strategies and stopping without exceptions.
    """

    def __init__(self, wait_random=None, wait_exponential=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wait_random = wait_random or tenacity.wait.wait_random(
            min=constants.getattr("OF_MIN_WAIT_SESSION_DEFAULT"),
            max=constants.getattr("OF_MAX_WAIT_SESSION_DEFAULT"),
        )
        self.wait_exponential = wait_exponential or tenacity.wait_exponential(
            min=constants.getattr("OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAUL"),
            max=constants.getattr("OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAUL"),
        )
        self.wait = self._wait_picker

    def _wait_picker(self, retry_state) -> None:
        exception = retry_state.outcome.exception()
        is_429 = (
            isinstance(exception, aiohttp.ClientResponseError)
            and getattr(exception, "status_code", None) == 429
        ) or (
            isinstance(exception, httpx.HTTPStatusError)
            and (
                getattr(exception.response, "status_code", None)
                or getattr(exception.response, "status", None)
            )
            == 429
        )
        if is_429:
            sleep = self.wait_exponential(retry_state)
        else:
            sleep = self.wait_random(retry_state)
        return sleep


class sessionManager:
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
        sem=None,
        retries=None,
        wait_min=None,
        wait_max=None,
        wait_min_exponential=None,
        wait_max_exponential=None,
        log=None,
        semaphore=None,
        sync_sem=None,
        sync_semaphore=None,
    ):
        connect_timeout = connect_timeout or constants.getattr("CONNECT_TIMEOUT")
        total_timeout = total_timeout or constants.getattr("TOTAL_TIMEOUT")
        read_timeout = read_timeout or constants.getattr("CHUNK_READ_TIMEOUT")
        pool_timeout = pool_timeout or constants.getattr("POOL_CONNECT_TIMEOUT")
        limit = limit or constants.getattr("MAX_CONNECTIONS")
        keep_alive = keep_alive or constants.getattr("KEEP_ALIVE")
        keep_alive_exp = keep_alive_exp or constants.getattr("KEEP_ALIVE_EXP")
        proxy = proxy or constants.getattr("PROXY")
        proxy_auth = proxy_auth or constants.getattr("PROXY_AUTH")
        self._backend = backend or data.get_backend()
        self._connect_timeout = connect_timeout
        self._total_timeout = total_timeout
        self._read_timeout = read_timeout
        self._pool_connect_timeout = pool_timeout
        self._connect_limit = limit
        self._keep_alive = keep_alive
        self._keep_alive_exp = keep_alive_exp
        self._proxy = proxy
        self._proxy_auth = proxy_auth
        self._delay = delay or 0
        self._sem = semaphore or asyncio.Semaphore(sem or 100000)
        self._sync_sem = sync_semaphore or threading.Semaphore(
            sync_sem or constants.getattr("SESSION_MANAGER_SYNC_SEM_DEFAULT")
        )
        self._retries = retries or constants.getattr("OF_NUM_RETRIES_SESSION_DEFAULT")
        self._wait_min = wait_min or constants.getattr("OF_MIN_WAIT_SESSION_DEFAULT")
        self._wait_max = wait_max or constants.getattr("OF_NUM_RETRIES_SESSION_DEFAULT")
        self._wait_min_exponential = wait_min_exponential or constants.getattr(
            "OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT"
        )
        self._wait_max_exponential = wait_max_exponential or constants.getattr(
            "OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT"
        )
        self._log = log or logging.getLogger("shared")

    async def __aenter__(self):
        self._async = True
        if self._backend == "aio":
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    total=self._total_timeout,
                    connect=self._connect_timeout,
                    sock_connect=self._pool_connect_timeout,
                    sock_read=self._read_timeout,
                ),
                connector=aiohttp.TCPConnector(limit=self._connect_limit),
            )
            self._request_func=self._aio_funct

        elif self._backend == "httpx":
            self._session = httpx.AsyncClient(
                http2=True,
                proxies=self._proxy,
                limits=httpx.Limits(
                    max_keepalive_connections=self._keep_alive,
                    max_connections=self._connect_limit,
                    keepalive_expiry=self._keep_alive_exp,
                ),
                timeout=httpx.Timeout(
                    self._total_timeout,
                    connect=self._connect_timeout,
                    pool=self._pool_connect_timeout,
                    read=self._read_timeout,
                ),
            )
            self._request_func=self._httpx_funct_async

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)

    def __enter__(self):
        self._async = False
        if self._backend == "httpx":
            self._session = httpx.Client(
                http2=True,
                proxies=self._proxy,
                limits=httpx.Limits(
                    max_keepalive_connections=self._keep_alive,
                    max_connections=self._connect_limit,
                    keepalive_expiry=self._keep_alive_exp,
                ),
                timeout=httpx.Timeout(
                    self._total_timeout,
                    connect=self._connect_timeout,
                    pool=self._pool_connect_timeout,
                    read=self._read_timeout,
                ),
            )
        elif self._backend == "aio":
            raise Exception("aiohttp is async only")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.__exit__(exc_type, exc_val, exc_tb)

    def _create_headers(self, headers, url, sign):
        headers = headers or {}
        headers.update(auth_requests.make_headers())
        headers = self._create_sign(headers, url) if sign is None else headers
        return headers

    def _create_sign(self, headers, url):
        auth_requests.create_sign(url, headers)
        return headers

    def _create_cookies(self):
        return auth_requests.add_cookies()

    @contextlib.contextmanager
    def requests(
        self,
        url=None,
        method="get",
        headers=None,
        cookies=None,
        json=None,
        params=None,
        redirects=True,
        data=None,
        sign=None,
        retries=None,
        wait_min=None,
        wait_max=None,
        log=None,
    ):
        headers = self._create_headers(headers, url, sign) if headers is None else None
        cookies = self._create_cookies() if cookies is None else None
        json = json or None
        params = params or None
        r = None
        log = log or self._log
        min = wait_min or self._wait_min
        max = wait_max or self._wait_max
        retries = retries or self._retries
        sync_sem = self._sync_sem or sync_sem
        for _ in Retrying(
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            stop=tenacity.stop.stop_after_attempt(retries),
            wait=tenacity.wait.wait_random(min=min, max=max),
            before=lambda x: (
                log.debug(f"[bold]attempt: {x.attempt_number}[bold] for {url}")
                if x.attempt_number > 1
                else None
            ),
            reraise=True,
        ):
            r = None
            with _:
                sync_sem.acquire()
                try:
                    r = self._httpx_funct(
                        method,
                        url=url,
                        follow_redirects=redirects,
                        params=params,
                        cookies=cookies,
                        headers=headers,
                        json=json,
                        data=data,
                    )
                    if r.status_code == 404:
                        pass
                    elif not r.ok:
                        log.debug(f"[bold]failed: [bold] {r.url}")
                        log.debug(f"[bold]status: [bold] {r.status}")
                        log.debug(f"[bold]response text [/bold]: {r.text_()}")
                        log.debug(f"[bold]headers[/bold]: {r.headers}")
                        r.raise_for_status()
                except Exception as E:
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    raise E
        yield r
        sync_sem.release()

    async def requests_async(
        self,
        url=None,
        wait_min=None,
        wait_max=None,
        wait_min_exponential=None,
        wait_max_exponential=None,
        retries=None,
        method="get",
        headers=None,
        cookies=None,
        json=None,
        params=None,
        redirects=True,
        data=None,
        sign=None,
        log=None,
        sem=None,
        *args,
        **kwargs,
    ):
        wait_min = wait_min or self._wait_min
        wait_max = wait_max or self._wait_max
        wait_min_exponential = wait_min_exponential or self._wait_min_exponential
        wait_max_exponential = wait_max_exponential or self._wait_max_exponential
        log = log or self._log
        retries = retries or self._retries
        sem = sem or self._sem
        async for _ in CustomTenacity(
            wait_exponential=tenacity.wait.wait_exponential(
                multiplier=2, min=wait_min_exponential, max=wait_max_exponential
            ),
            wait_random=tenacity.wait_random(min=wait_min, max=wait_max),
            stop=tenacity.stop.stop_after_attempt(retries),
            before=lambda x: (
                log.debug(f"[bold]attempt: {x.attempt_number}[bold] for {url}")
                if x.attempt_number > 1
                else None
            ),
            reraise=True,
        ):
            with _:
                await sem.acquire()
                headers = (
                self._create_headers(headers, url, sign)
                        if headers is None
                        else headers
                )
                cookies = self._create_cookies() if cookies is None else None

                self._request_func(method,url,sem,log,
                            headers=headers,
                            cookies=cookies,
                            redirects=redirects,
                            params=params,
                            json=json)
        sem.release()

    @contextlib.asynccontextmanager
    async def _httpx_funct_async(self,method,url,sem,log, *args, **kwargs):
        try:
            r = await self._session.request(method,url,*args, **kwargs)
            r.ok = not r.is_error
            r.json_ = lambda: self.factoryasync(r.json)
            r.text_ = lambda: self.factoryasync(r.text)
            r.status = r.status_code
            r.iter_chunked = r.aiter_bytes
            r.read = r.aread
            if r.status==404:
                pass
            elif not r.ok:
                r.raise_for_status()
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            sem.release()
            raise E
        yield r
    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input
    def _httpx_funct(self, method, **kwargs):
        r = self._session.request(method.upper(), **kwargs)
        r.ok = not r.is_error
        r.json_ = r.json
        r.text_ = lambda: r.text
        r.status = r.status_code
        r.iter_chunked = r.iter_bytes
        return r

    async def _aio_funct(self, method,url,sem,log, *args, **kwargs):
        # public function forces context manager use
        async with self._session.request(method,url, *args, **kwargs) as r:
            try:
                r.text_ = r.text
                r.json_ = r.json
                r.iter_chunked = r.content.iter_chunked
                r.status_code = r.status
                r.read = r.content.read
                if r.status==404:
                    pass
                elif not r.ok:
                    r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                sem.release()
                raise E
            yield r


