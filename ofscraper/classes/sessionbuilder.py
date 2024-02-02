import contextlib
import functools
import ssl

import aiohttp
import certifi
import httpx

import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants

from ..utils import auth

####
#  This class allows the user to select which backend aiohttp or httpx they want to use
#  httpx has better compatiblilty but is slower
#
#####


class sessionBuilder:
    def __init__(
        self,
        backend=None,
        set_header=True,
        set_sign=True,
        set_cookies=True,
        connect_timeout=None,
        total_timeout=None,
        read_timeout=None,
        pool_timeout=None,
        limit=None,
        keep_alive=None,
        keep_alive_exp=None,
        proxy=None,
        proxy_auth=None,
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
        self._set_cookies = set_cookies
        self._set_header = set_header
        self._set_sign = set_sign
        self._connect_timeout = connect_timeout
        self._total_timeout = total_timeout
        self._read_timeout = read_timeout
        self._pool_connect_timeout = pool_timeout
        self._connect_limit = limit
        self._keep_alive = keep_alive
        self._keep_alive_exp = keep_alive_exp
        self._proxy = proxy
        self._proxy_auth = proxy_auth

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

    def _create_headers(self, headers, url):
        headers = headers or {}
        if self._set_header:
            new_headers = auth.make_headers(auth.read_auth())
            headers.update(new_headers)
        headers = self._create_sign(headers, url)
        return headers

    def _create_sign(self, headers, url):
        auth.create_sign(url, headers) if self._set_sign else None
        return headers

    def _create_cookies(self):
        return auth.add_cookies()

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
    ):
        headers = self._create_headers(headers, url)
        cookies = cookies or self._create_cookies()
        json = json or None
        params = params or None

        if self._backend == "aio":
            funct = functools.partial(
                self._aio_funct_async,
                method,
                url=url,
                headers=headers,
                cookies=cookies,
                allow_redirects=redirects,
                proxy=self._proxy,
                proxy_auth=self._proxy_auth,
                params=params,
                json=json,
                data=data,
                ssl=ssl.create_default_context(cafile=certifi.where()),
            )

        # elif self._backend=="httpx" and self._async:
        #     funct=functools.partial(self._httpx_funct_async,method,url=url,follow_redirects=redirects,params=params,cookies=cookies,headers=headers,json=json,data=data)

        elif self._backend == "httpx" and self._async:
            inner_func = functools.partial(
                self._session.request,
                method,
                follow_redirects=redirects,
                url=url,
                cookies=cookies,
                headers=headers,
                json=json,
                params=params,
            )
            funct = functools.partial(self._httpx_funct_async, inner_func)

        elif self._backend == "httpx" and not self._async:
            funct = functools.partial(
                self._httpx_funct,
                method,
                url=url,
                follow_redirects=redirects,
                params=params,
                cookies=cookies,
                headers=headers,
                json=json,
                data=data,
            )

        return funct

    # context providers are used to provide access to object before exit
    @contextlib.asynccontextmanager
    async def _httpx_funct_async(self, funct):
        t = await funct()
        t.ok = not t.is_error
        t.json_ = lambda: self.factoryasync(t.json)
        t.text_ = lambda: self.factoryasync(t.text)
        t.status = t.status_code
        t.iter_chunked = t.aiter_bytes
        yield t
        None

    # context providers are used to provide access to object before exit
    @contextlib.contextmanager
    def _httpx_funct(self, method, **kwargs):
        try:
            t = self._session.request(method.upper(), **kwargs)
        except Exception as E:
            raise E

        t.ok = not t.is_error
        t.json_ = t.json
        t.text_ = lambda: t.text
        t.status = t.status_code
        t.iter_chunked = t.iter_bytes
        yield t
        None

    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input

    # context providers are used to provide access to object before exit
    @contextlib.asynccontextmanager
    async def _aio_funct_async(self, method, **kwargs):
        try:
            resp = self._session.request(method, **kwargs)
        except Exception as E:
            raise E
        async with resp as r:
            r.text_ = r.text
            r.json_ = r.json
            r.iter_chunked = r.content.iter_chunked
            yield r

        None
