import asyncio
import contextlib
import logging
import ssl
import threading
import time
import traceback

import aiohttp
import aiohttp.client_exceptions
import arrow
import certifi
import httpx
import tenacity
from tenacity import AsyncRetrying, Retrying, retry_if_not_exception_type

import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants


def is_rate_limited(exception):
    return (
        isinstance(exception, aiohttp.ClientResponseError)
        and (
            getattr(exception, "status_code", None)
            or getattr(exception, "status", None) in {429, 504}
        )
    ) or (
        isinstance(exception, httpx.HTTPStatusError)
        and (
            (
                getattr(exception.response, "status_code", None)
                or getattr(exception.response, "status", None)
            )
            in {429, 504}
        )
    )


class SessionSleep:
    def __init__(self, sleep=None):
        self._sleep = sleep
        self._last_date = arrow.now()
        self._alock = asyncio.Lock()

    async def async_toomany_req(self):
        async with self._alock:
            self.toomany_req()

    def toomany_req(self):
        log = logging.getLogger("shared")
        dif_min = constants.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF")
        if self._sleep is None:
            self._sleep = constants.getattr("SESSION_SLEEP_INIT")
            log.debug(f"too many req => setting sleep to init [{self._sleep} seconds]")
        elif arrow.now().float_timestamp - self._last_date.float_timestamp < dif_min:
            log.debug(
                f"too many req => not changing sleep [{self._sleep} seconds] because last call less than {dif_min} seconds"
            )
            return self._sleep
        else:
            self._sleep = self._sleep * 2
            log.debug(f"too many req => setting sleep to [{self._sleep} seconds]")
        self._last_date = arrow.now()
        return self._sleep

    async def async_do_sleep(self):
        if self._sleep:
            logging.getLogger("shared").debug(
                f"too many req => waiting [{self._sleep} seconds] before next req"
            )
            await asyncio.sleep(self._sleep)

    def do_sleep(self):
        if self._sleep:
            logging.getLogger("shared").debug(
                f"too many req => waiting [{self._sleep} seconds] before next req"
            )
            time.sleep(self._sleep)

    @property
    def sleep(self):
        return self._sleep

    @sleep.setter
    def sleep(self, val):
        self._sleep = val


class CustomTenacity(AsyncRetrying):
    """
    A custom context manager using tenacity for asynchronous retries with wait strategies and stopping without exceptions.
    """

    def __init__(self, wait_random=None, wait_exponential=None, *args, **kwargs):
        super().__init__(*args, after=self._after_func, **kwargs)
        self.wait_random = wait_random or tenacity.wait.wait_random(
            min=constants.getattr("OF_MIN_WAIT_SESSION_DEFAULT"),
            max=constants.getattr("OF_MAX_WAIT_SESSION_DEFAULT"),
        )
        self.wait_exponential = wait_exponential or tenacity.wait_exponential(
            min=constants.getattr("OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT"),
            max=constants.getattr("OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT"),
        )
        self.wait = self._wait_picker

    def _wait_picker(self, retry_state) -> None:
        exception = retry_state.outcome.exception()
        # if is_rate_limited(exception):
        #     sleep = self.wait_exponential(retry_state)
        # else:
        #     sleep = self.wait_random(retry_state)
        sleep = self.wait_random(retry_state)
        logging.getLogger("shared").debug(f"sleeping for {sleep} seconds before retry")
        return sleep

    def _after_func(self, retry_state) -> None:
        exception = retry_state.outcome.exception()
        if (
            isinstance(exception, (aiohttp.ClientResponseError, aiohttp.ClientError))
            and (
                getattr(exception, "status_code", None)
                or getattr(exception, "status", None)
            )
            == 403
        ) or (
            isinstance(exception, httpx.HTTPStatusError)
            and (
                getattr(exception.response, "status_code", None)
                or getattr(exception.response, "status", None)
            )
            == 403
        ):
            auth_requests.read_request_auth(forced=True)


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
        new_request_auth=False,
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
        self._delay = delay or 0
        self._sem = semaphore or asyncio.BoundedSemaphore(sem or 100000)
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
        auth_requests.read_request_auth(forced=None) if new_request_auth else None
        self._sleeper = SessionSleep()

    async def __aenter__(self):
        self._async = True
        if self._backend == "aio":
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=self._connect_limit),
            )

        elif self._backend == "httpx":
            self._session = httpx.AsyncClient(
                http2=True,
                proxies=self._proxy,
                limits=httpx.Limits(
                    max_keepalive_connections=self._keep_alive,
                    max_connections=self._connect_limit,
                    keepalive_expiry=self._keep_alive_exp,
                ),
            )

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
        total_timeout=None,
        connect_timeout=None,
        pool_connect_timeout=None,
        read_timeout=None,
        sync_sem=None,
        sleeper=None,
    ):
        auth_requests.read_request_auth(forced=True) if sign else None

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
        sleeper = sleeper or self._sleeper
        for _ in Retrying(
            retry=retry_if_not_exception_type(
                (KeyboardInterrupt, asyncio.TimeoutError)
            ),
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
                sleeper.do_sleep()
                try:
                    r = self._httpx_funct(
                        method,
                        timeout=httpx.Timeout(
                            total_timeout or self._total_timeout,
                            connect=connect_timeout or self._connect_timeout,
                            pool=pool_connect_timeout or self._pool_connect_timeout,
                            read=read_timeout or self._read_timeout,
                        ),
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
                    if is_rate_limited(E):
                        sleeper.toomany_req()
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    raise E
        yield r
        sync_sem.release()

    @contextlib.asynccontextmanager
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
        total_timeout=None,
        connect_timeout=None,
        pool_connect_timeout=None,
        read_timeout=None,
        sleeper=None,
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
        sleeper = sleeper or self._sleeper
        async for _ in CustomTenacity(
            wait_exponential=tenacity.wait.wait_exponential(
                multiplier=2, min=wait_min_exponential, max=wait_max_exponential
            ),
            retry=retry_if_not_exception_type(
                (KeyboardInterrupt, asyncio.TimeoutError)
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
                r = None
                await sem.acquire()
                await sleeper.async_do_sleep()
                try:
                    headers = (
                        self._create_headers(headers, url, sign)
                        if headers is None
                        else headers
                    )
                    cookies = self._create_cookies() if cookies is None else None
                    json = json
                    params = params
                    if self._backend == "aio":
                        r = await self._aio_funct(
                            method,
                            url,
                            timeout=aiohttp.ClientTimeout(
                                total=total_timeout or self._total_timeout,
                                connect=connect_timeout or self._connect_timeout,
                                sock_connect=pool_connect_timeout
                                or self._pool_connect_timeout,
                                sock_read=read_timeout or self._read_timeout,
                            ),
                            headers=headers,
                            cookies=cookies,
                            allow_redirects=redirects,
                            proxy=self._proxy,
                            params=params,
                            json=json,
                            data=data,
                            ssl=ssl.create_default_context(cafile=certifi.where()),
                        )
                    else:
                        r = await self._httpx_funct_async(
                            method,
                            timeout=httpx.Timeout(
                                total_timeout or self._total_timeout,
                                connect=connect_timeout or self._connect_timeout,
                                pool=pool_connect_timeout or self._pool_connect_timeout,
                                read=read_timeout or self._read_timeout,
                            ),
                            follow_redirects=redirects,
                            url=url,
                            cookies=cookies,
                            headers=headers,
                            json=json,
                            params=params,
                            data=data,
                        )
                    if r.status_code == 404:
                        pass
                    elif not r.ok:
                        log.debug(f"[bold]failed: [bold] {r.url}")
                        log.debug(f"[bold]status: [bold] {r.status}")
                        log.debug(f"[bold]response text [/bold]: {await r.text_()}")
                        log.debug(f"[bold]headers[/bold]: {r.headers}")
                        r.raise_for_status()
                except Exception as E:
                    if is_rate_limited(E):
                        await sleeper.async_toomany_req()
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    sem.release()
                    raise E
        yield r
        sem.release()

    @property
    def sleep(self):
        return self._sleeper._sleep

    @sleep.setter
    def sleep(self, val):
        self._sleeper._sleep = val

    async def _httpx_funct_async(self, *args, **kwargs):
        t = await self._session.request(*args, **kwargs)
        t.ok = not t.is_error
        t.json_ = lambda: self.factoryasync(t.json)
        t.text_ = lambda: self.factoryasync(t.text)
        t.status = t.status_code
        t.iter_chunked = t.aiter_bytes
        t.read_ = t.aread
        return t

    def _httpx_funct(self, method, **kwargs):
        t = self._session.request(method.upper(), **kwargs)
        t.ok = not t.is_error
        t.json_ = t.json
        t.text_ = lambda: t.text
        t.status = t.status_code
        t.iter_chunked = t.iter_bytes
        t.read_ = t.read
        return t

    async def _aio_funct(self, method, *args, **kwargs):
        # public function forces context manager use
        r = await self._session._request(method, *args, **kwargs)
        r.text_ = r.text
        r.json_ = r.json
        r.iter_chunked = r.content.iter_chunked
        r.status_code = r.status
        r.read_ = r.content.read
        return r

    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input
