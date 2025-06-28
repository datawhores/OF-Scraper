import asyncio
import logging
import threading
import time
import ssl
import certifi
import contextlib
import traceback
from typing import Optional, Dict, Union, AsyncGenerator, Any, Generator

import arrow
import httpx
import tenacity
import aiohttp
from tenacity import AsyncRetrying, Retrying, retry_if_not_exception_type
from httpx_aiohttp import AiohttpTransport
from aiohttp import ClientSession

import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.env.env as env
from ofscraper.utils.auth.utils.warning.print import print_auth_warning
import ofscraper.utils.settings as settings

# Constants for request actions
TOO_MANY = "too_many"
AUTH = "auth"
FORBIDDEN = "forbidden"
FORCED_NEW = "get_new_sign"
SIGN = "get_sign"
COOKIES = "get_cookies_str"
HEADERS = "create_header"


def is_provided_exception_number(exception: Exception, *numbers: int) -> bool:
    """Utility to check if an exception's status code matches given numbers."""
    status_code = None
    if isinstance(exception, aiohttp.ClientResponseError):
        status_code = getattr(exception, "status_code", None) or getattr(exception, "status", None)
    elif isinstance(exception, httpx.HTTPStatusError):
        status_code = getattr(exception.response, "status_code", None)
    return status_code in numbers


class SessionSleep:
    """
    Manages dynamic sleep intervals to handle API rate-limiting.
    """
    def __init__(
        self,
        sleep: Optional[float] = None,
        difmin: Optional[int] = None,
        max_sleep: Optional[float] = None,
        decay_threshold: Optional[float] = None,
        decay_factor: Optional[float] = None,
        increase_factor: Optional[float] = None,
    ):
        self._sleep = None
        self._last_date = arrow.now()
        self._alock = asyncio.Lock()
        self._lock=threading.Lock()
        self._init_sleep = sleep if sleep is not None else env.getattr("SESSION_SLEEP_INIT")
        self._difmin = difmin if difmin is not None else env.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF")
        self._max_sleep = max_sleep if max_sleep is not None else env.getattr("SESSION_SLEEP_MAX")
        self._increase_factor = increase_factor if increase_factor is not None else env.getattr("SESSION_SLEEP_INCREASE_FACTOR")
        self._decay_threshold = decay_threshold if decay_threshold is not None else env.getattr("SESSION_SLEEP_DECAY_THRESHOLD")
        self._decay_factor = decay_factor if decay_factor is not None else env.getattr("SESSION_SLEEP_DECAY_FACTOR")

    def _maybe_decay_sleep(self):
        if not self._sleep or self._sleep <= self._init_sleep:
            return
        if (arrow.now() - self._last_date).total_seconds() > self._decay_threshold:
            new_sleep = self._sleep / self._decay_factor
            self._sleep = max(self._init_sleep, new_sleep)
            self._last_date = arrow.now()
            logging.getLogger("shared").debug(f"Sleep decay => Reducing sleep to [{self._sleep:.2f} seconds]")

    async def async_do_sleep(self):
        async with self._alock:
            self._maybe_decay_sleep()
        if self._sleep and self._sleep > 0:
            logging.getLogger("shared").debug(f"Waiting [{self._sleep:.2f} seconds] due to recent errors")
            await asyncio.sleep(self._sleep)

    def do_sleep(self):
        with self._lock:
             self._maybe_decay_sleep()
        if self._sleep and self._sleep > 0:
            logging.getLogger("shared").debug(f"Waiting [{self._sleep:.2f} seconds] due to recent errors")
            time.sleep(self._sleep)

    def toomany_req(self):
        log = logging.getLogger("shared")
        if not self._sleep: 
            self._sleep = self._init_sleep if self._init_sleep > 0 else 1
            log.debug(f"Backoff triggered => setting sleep to starting value: [{self._sleep:.2f} seconds]")
        elif (arrow.now().float_timestamp - self._last_date.float_timestamp < self._difmin):
            log.debug(f"Backoff => not changing sleep [{self._sleep:.2f} seconds], last error was less than {self._difmin}s ago")
            return
        else:
            new_sleep = self._sleep * self._increase_factor
            self._sleep = min(new_sleep, self._max_sleep)
            log.debug(f"Backoff => increasing sleep by factor x{self._increase_factor} to: [{self._sleep:.2f} seconds]")
        self._last_date = arrow.now()

    def reset_sleep(self):
        self._sleep = self._init_sleep
        self._last_date = arrow.now()

    async def async_toomany_req(self):
        async with self._alock:
            self.toomany_req()

    @property
    def sleep(self) -> Optional[float]:
        return self._sleep

    @sleep.setter
    def sleep(self, val: float) -> None:
        self._sleep = val

class CustomTenacity(AsyncRetrying):
    """
    A custom context manager using tenacity for asynchronous retries.
    """
    def __init__(self, wait_random=None, wait_exponential=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wait_random = wait_random or tenacity.wait.wait_random(
            min=env.getattr("OF_MIN_WAIT_SESSION_DEFAULT"),
            max=env.getattr("OF_MAX_WAIT_SESSION_DEFAULT"),
        )
        self.wait_exponential = wait_exponential or tenacity.wait_exponential(
            min=env.getattr("OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT"),
            max=env.getattr("OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT"),
        )
        self.wait = self._wait_picker

    def _wait_picker(self, retry_state: "tenacity.RetryCallState") -> None:
        sleep = self.wait_random(retry_state)
        logging.getLogger("shared").debug(f"sleeping for {sleep} seconds before retry")
        return sleep

class sessionManager:
    """
    Manages HTTP sessions, handling pooling, signing, retries, and dual backoff systems.
    """
    def __init__(
        self,
        # --- Standard session parameters ---
        connect_timeout: Optional[int] = None,
        total_timeout: Optional[int] = None,
        read_timeout: Optional[int] = None,
        pool_timeout: Optional[int] = None,
        limit: Optional[int] = None,
        keep_alive: Optional[int] = None,
        keep_alive_exp: Optional[int] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[Dict] = None,
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

        # --- Parameters for the 429/504 Rate Limit Sleeper ---
        rate_limit_sleep: Optional[float] = None,
        rate_limit_difmin: Optional[int] = None,
        rate_limit_max_sleep: Optional[float] = None,
        rate_limit_decay_threshold: Optional[float] = None,
        rate_limit_decay_factor: Optional[float] = None,
        rate_limit_increase_factor: Optional[float] = None,
        
        # --- Parameters for the 403 Forbidden Sleeper ---
        forbidden_sleep: Optional[float] = None,
        forbidden_difmin: Optional[int] = None,
        forbidden_max_sleep: Optional[float] = None,
        forbidden_decay_threshold: Optional[float] = None,
        forbidden_decay_factor: Optional[float] = None,
        forbidden_increase_factor: Optional[float] = None,
    ):
        self._connect_timeout = connect_timeout if connect_timeout is not None else env.getattr("CONNECT_TIMEOUT")
        self._total_timeout = total_timeout if total_timeout is not None else env.getattr("TOTAL_TIMEOUT")
        self._read_timeout = read_timeout if read_timeout is not None else env.getattr("OF_READ_TIMEOUT")
        self._pool_connect_timeout = pool_timeout if pool_timeout is not None else env.getattr("POOL_CONNECT_TIMEOUT")
        self._connect_limit = limit if limit is not None else env.getattr("MAX_CONNECTIONS")
        self._keep_alive = keep_alive if keep_alive is not None else env.getattr("KEEP_ALIVE")
        self._keep_alive_exp = keep_alive_exp if keep_alive_exp is not None else env.getattr("KEEP_ALIVE_EXP")
        self._proxy = proxy if proxy is not None else env.getattr("PROXY")
        
        self._sem = sem or asyncio.BoundedSemaphore(sem_count if sem_count is not None else env.getattr("SESSION_MANAGER_SEM_DEFAULT"))
        self._sync_sem = sync_sem or threading.Semaphore(sync_sem_count if sync_sem_count is not None else env.getattr("SESSION_MANAGER_SYNC_SEM_DEFAULT"))
        
        self._retries = retries if retries is not None else env.getattr("OF_NUM_RETRIES_SESSION_DEFAULT")
        self._wait_min = wait_min if wait_min is not None else env.getattr("OF_MIN_WAIT_SESSION_DEFAULT")
        self._wait_max = wait_max if wait_max is not None else env.getattr("OF_MAX_WAIT_SESSION_DEFAULT")
        self._wait_min_exponential = wait_min_exponential if wait_min_exponential is not None else env.getattr("OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT")
        self._wait_max_exponential = wait_max_exponential if wait_max_exponential is not None else env.getattr("OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT")

        self._log = log or logging.getLogger("shared")
        
        self._rate_limit_sleeper = SessionSleep(
            sleep=rate_limit_sleep, difmin=rate_limit_difmin, max_sleep=rate_limit_max_sleep,
            decay_threshold=rate_limit_decay_threshold, decay_factor=rate_limit_decay_factor,
            increase_factor=rate_limit_increase_factor,
        )
        
        self._forbidden_sleeper = SessionSleep(
            sleep=forbidden_sleep if forbidden_sleep is not None else env.getattr("SESSION_403_SLEEP_INIT"),
            difmin=forbidden_difmin if forbidden_difmin is not None else env.getattr("SESSION_403_SLEEP_INCREASE_TIME_DIFF"),
            max_sleep=forbidden_max_sleep if forbidden_max_sleep is not None else env.getattr("SESSION_403_SLEEP_MAX"),
            decay_threshold=forbidden_decay_threshold if forbidden_decay_threshold is not None else env.getattr("SESSION_403_SLEEP_DECAY_THRESHOLD"),
            decay_factor=forbidden_decay_factor if forbidden_decay_factor is not None else env.getattr("SESSION_403_SLEEP_DECAY_FACTOR"),
            increase_factor=forbidden_increase_factor if forbidden_increase_factor is not None else env.getattr("SESSION_403_SLEEP_INCREASE_FACTOR"),
        )
        self._session: Union[httpx.AsyncClient, httpx.Client, None] = None
        self._async: bool = True
        self._last_auth_warn_date = arrow.now()

    def print_auth_warning(self, E: Exception):
        if (arrow.now() - self._last_auth_warn_date).total_seconds() > env.getattr("auth_warning_timeout"):
            print_auth_warning(E)
            self._last_auth_warn_date = arrow.now()

    def _handle_error(self, E: Exception, exceptions: list):
        if TOO_MANY in exceptions and is_provided_exception_number(E, 429, 504):
            self._rate_limit_sleeper.toomany_req()
        elif FORBIDDEN in exceptions and is_provided_exception_number(E, 403):
            self.print_auth_warning(E)
            self._forbidden_sleeper.toomany_req()
        elif AUTH in exceptions and is_provided_exception_number(E, 400, 401):
            self.print_auth_warning(E)
            time.sleep(8)
    
    async def _async_handle_error(self, E: Exception, exceptions: list):
        if TOO_MANY in exceptions and is_provided_exception_number(E, 429, 504):
            await self._rate_limit_sleeper.async_toomany_req()
        elif FORBIDDEN in exceptions and is_provided_exception_number(E, 403):
            self.print_auth_warning(E)
            await self._forbidden_sleeper.async_toomany_req()
        elif AUTH in exceptions and is_provided_exception_number(E, 400, 401):
            self.print_auth_warning(E)
            await asyncio.sleep(8)

    def _set_session(self, async_=True):
        if self._session:
            return
        if async_:
            self._session = httpx.AsyncClient(
                http2=True,
                proxy=self._proxy,
                limits=httpx.Limits(
                    max_keepalive_connections=self._keep_alive,
                    max_connections=self._connect_limit,
                    keepalive_expiry=self._keep_alive_exp,
                ),
                transport=AiohttpTransport(
                    client=lambda: ClientSession(
                        proxy=self._proxy,
                        connector=aiohttp.TCPConnector(
                            limit=self._connect_limit,
                            ssl=False if not settings.get_settings().ssl_validation else ssl.create_default_context(cafile=certifi.where())
                        ),
                    )
                )
            )
        else:
            self._session = httpx.Client(
                http2=True,
                proxy=self._proxy,
                limits=httpx.Limits(
                    max_keepalive_connections=self._keep_alive,
                    max_connections=self._connect_limit,
                    keepalive_expiry=self._keep_alive_exp,
                ),
            )
        self._async = async_
        return self._session

    async def __aenter__(self):
        self._set_session(async_=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.__aexit__(exc_type, exc_val, exc_tb)

    def __enter__(self):
        self._set_session(async_=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.__exit__(exc_type, exc_val, exc_tb)
        time.sleep(1)

    def _create_headers(self, headers, url, sign, forced):
        headers = headers or {}
        headers.update(auth_requests.make_headers())
        if sign:
            auth_requests.create_sign(url, headers)
        return headers

    def _create_cookies(self):
        return auth_requests.add_cookies()

    def reset_sleep(self):
        self._rate_limit_sleeper.reset_sleep()
        self._forbidden_sleeper.reset_sleep()

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
        actions: Optional[list] = None,
        exceptions: Optional[list] = None,
        **kwargs: Any
    ) -> Generator[httpx.Response, None, None]:
        actions = actions or []
        exceptions = exceptions or []
        log = kwargs.get("log") or self._log
        retries = kwargs.get("retries") or self._retries
        wait_min = kwargs.get("wait_min") or self._wait_min
        wait_max = kwargs.get("wait_max") or self._wait_max

        for _ in Retrying(
            retry=retry_if_not_exception_type((KeyboardInterrupt, SystemExit)),
            stop=tenacity.stop.stop_after_attempt(retries),
            wait=tenacity.wait.wait_random(min=wait_min, max=wait_max),
            before=lambda x: (log.debug(f"[bold]attempt: {x.attempt_number}[bold] for {url}") if x.attempt_number > 1 else None),
            reraise=True,
        ):
            r = None
            with self._sync_sem:
                with _:
                    try:
                        self._rate_limit_sleeper.do_sleep()
                        self._forbidden_sleeper.do_sleep()
                        
                        if SIGN in actions or FORCED_NEW in actions or HEADERS in actions:
                            headers = self._create_headers(headers, url, SIGN in actions, FORCED_NEW in actions)
                        if COOKIES in actions:
                            cookies = self._create_cookies()

                        r = self._httpx_funct(
                            method, url=url, follow_redirects=redirects, params=params, cookies=cookies,
                            headers=headers, json=json, data=data,
                            timeout=httpx.Timeout(
                                kwargs.get("total_timeout") or self._total_timeout,
                                connect=kwargs.get("connect_timeout") or self._connect_timeout,
                                pool=kwargs.get("pool_connect_timeout") or self._pool_connect_timeout,
                                read=kwargs.get("read_timeout") or self._read_timeout
                            ),
                        )

                        if not r.ok and r.status_code != 404:
                            log.debug(f"[bold]failed: [bold] {r.url}")
                            log.debug(f"[bold]status: [bold] {r.status_code}")
                            log.debug(f"[bold]response text [/bold]: {r.text_()}")
                            log.debug(f"response headers {dict(r.headers)}")
                            log.debug(f"requests headers {dict(r.request.headers)}")
                            r.raise_for_status()

                    except Exception as E:
                        self._log.traceback_(E)
                        self._log.traceback_(traceback.format_exc())
                        self._handle_error(E, exceptions)
                        raise E
        yield r

    @contextlib.asynccontextmanager
    async def requests_async(
        self,
        url: str = None,
        method: str = "get",
        headers: dict = None,
        cookies: dict = None,
        json: dict = None,
        params: dict = None,
        data: dict = None,
        actions: Optional[list] = None,
        exceptions: Optional[list] = None,
        **kwargs,
    ) -> AsyncGenerator[httpx.Response, None]:
        actions = actions or []
        exceptions = exceptions or []
        retries = kwargs.get("retries") or self._retries
        wait_min = kwargs.get("wait_min") or self._wait_min
        wait_max_exponential = kwargs.get("wait_max_exponential") or self._wait_max_exponential
        
        async for _ in CustomTenacity(
            stop=tenacity.stop.stop_after_attempt(retries),
            wait=tenacity.wait.wait_random_exponential(multiplier=wait_min, max=wait_max_exponential),
            retry=retry_if_not_exception_type((KeyboardInterrupt, SystemExit)),
            reraise=True,
            before=lambda x: (self._log.debug(f"[bold]attempt: {x.attempt_number}[bold] for {url}") if x.attempt_number > 1 else None)
        ):
            with _:
                await self._sem.acquire()
                try:
                    await self._rate_limit_sleeper.async_do_sleep()
                    await self._forbidden_sleeper.async_do_sleep()

                    if SIGN in actions or FORCED_NEW in actions or HEADERS in actions:
                        headers = self._create_headers(headers, url, SIGN in actions, FORCED_NEW in actions)
                    if COOKIES in actions:
                        cookies = self._create_cookies()

                    r = await self._httpx_funct_async(
                        method, url=url, cookies=cookies, headers=headers, json=json, params=params, data=data,
                        timeout=httpx.Timeout(
                            kwargs.get("total_timeout") or self._total_timeout,
                            connect=kwargs.get("connect_timeout") or self._connect_timeout,
                            pool=kwargs.get("pool_connect_timeout") or self._pool_connect_timeout,
                            read=kwargs.get("read_timeout") or self._read_timeout
                        ),
                        follow_redirects=kwargs.get("redirects", True),
                    )

                    if not r.ok and r.status_code != 404:
                        self._log.debug(f"[bold]failed: [bold] {r.url}")
                        self._log.debug(f"[bold]status: [bold] {r.status_code}")
                        self._log.debug(f"[bold]response text [/bold]: {await r.text_()}")
                        self._log.debug(f"response headers {dict(r.headers)}")
                        r.raise_for_status()
                    
                    self._sem.release()
                    yield r
                    return
                except Exception as E:
                    await self._async_handle_error(E, exceptions)
                    self._sem.release()
                    raise E

    @contextlib.asynccontextmanager
    async def requests_async_stream(
        self,
        url: str = None,
        method: str = "get",
        headers: dict = None,
        cookies: dict = None,
        json: dict = None,
        params: dict = None,
        data: dict = None,
        actions: Optional[list] = None,
        exceptions: Optional[list] = None,
        **kwargs,
    ) -> AsyncGenerator[httpx.Response, None]:
        actions = actions or []
        exceptions = exceptions or []
        retries = kwargs.get("retries") or self._retries
        wait_min = kwargs.get("wait_min") or self._wait_min
        wait_max_exponential = kwargs.get("wait_max_exponential") or self._wait_max_exponential
        r = None
        
        async for _ in CustomTenacity(
            stop=tenacity.stop.stop_after_attempt(retries),
            wait=tenacity.wait.wait_random_exponential(multiplier=wait_min, max=wait_max_exponential),
            retry=retry_if_not_exception_type((KeyboardInterrupt, SystemExit)),
            reraise=True,
            before=lambda x: (self._log.debug(f"[bold]attempt: {x.attempt_number}[bold] for {url}") if x.attempt_number > 1 else None)
        ):
            await self._sem.acquire()
            try:
                with _:
                    await self._rate_limit_sleeper.async_do_sleep()
                    await self._forbidden_sleeper.async_do_sleep()

                    if SIGN in actions or FORCED_NEW in actions or HEADERS in actions:
                        headers = self._create_headers(headers, url, SIGN in actions, FORCED_NEW in actions)
                    if COOKIES in actions:
                        cookies = self._create_cookies()

                    r = await self._httpx_funct_async_stream(
                        method, url=url, cookies=cookies, headers=headers, json=json, params=params, data=data,
                        timeout=httpx.Timeout(
                            kwargs.get("total_timeout") or self._total_timeout,
                            connect=kwargs.get("connect_timeout") or self._connect_timeout,
                            pool=kwargs.get("pool_connect_timeout") or self._pool_connect_timeout,
                            read=kwargs.get("read_timeout") or self._read_timeout
                        ),
                        follow_redirects=kwargs.get("redirects", True),
                    )

                    if not r.ok and r.status_code != 404:
                        self._log.debug(f"[bold]failed: [bold] {r.url}")
                        self._log.debug(f"[bold]status: [bold] {r.status_code}")
                        self._log.debug(f"response headers {dict(r.headers)}")
                        r.raise_for_status()
                    
                    yield r
                    return
            except Exception as E:
                if r:
                    await r.aclose()
                await self._async_handle_error(E, exceptions)
                raise E
            finally:
                self._sem.release()


    @property
    def sleep(self):
        return self._rate_limit_sleeper.sleep

    @sleep.setter
    def sleep(self, val):
        self._rate_limit_sleeper.sleep = val

    async def _httpx_funct_async(self, *args, **kwargs):
        t = await self._session.request(*args, **kwargs)
        t.ok = not t.is_error
        async def json_wrapper(): return t.json()
        t.json_ = json_wrapper
        async def text_wrapper(): return t.text
        t.text_ = text_wrapper
        t.status = t.status_code
        t.iter_chunked = t.aiter_bytes
        t.read_ = t.aread
        return t
    
    async def _httpx_funct_async_stream(self, *args, **kwargs):
        auth=kwargs.pop("auth",None)
        follow_redirects=kwargs.pop("follow_redirects",None)
        req=self._session.build_request(*args, **kwargs)
        t = await self._session.send(
            request=req,
            follow_redirects=follow_redirects,
            stream=True,
            auth=auth,
        )
        t.ok = not t.is_error
        async def json_wrapper():
            await t.aread()
            return t.json()
        t.json_ = json_wrapper
        async def text_wrapper():
            await t.aread()
            return t.text
        t.text_ = text_wrapper
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
