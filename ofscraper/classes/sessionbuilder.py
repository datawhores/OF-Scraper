import contextlib
import functools
import ssl

import aiohttp
import certifi
import httpx
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.classes.semaphoreDelayed as semdelayed

####
#  This class allows the user to select which backend aiohttp or httpx they want to use
#  httpx has better compatiblilty but is slower
#
#####



class sessionBuilder:
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
        sems=None
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
        self._sem=semdelayed.semaphoreDelayed(sems=sems,delay=delay)

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

    def _create_headers(self, headers, url,sign):
        headers = headers or {}
        new_headers = auth_requests.make_headers()
        headers.update(new_headers)
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
        sign=None
    ):
        headers = self._create_headers(headers, url,sign) if headers is None else None
        cookies = self._create_cookies() if cookies is None else None
        json = json or None
        params = params or None
        t=self._httpx_funct(
                method,
                url=url,
                follow_redirects=redirects,
                params=params,
                cookies=cookies,
                headers=headers,
                json=json,
                data=data)
        yield t
    @contextlib.asynccontextmanager
    async def requests_async(
        self,
        url=None,
        method="get",
        headers=None,
        cookies=None,
        json=None,
        params=None,
        redirects=True,
        data=None,
        sign=None
    ):
        await self._sem.acquire()
        try:
            headers = self._create_headers(headers, url,sign) if headers is None else None
            cookies = self._create_cookies() if cookies is None else None
            json = json or None
            params = params or None
            if self._backend == "aio":
                r=await self._aio_funct(
                    method,
                    url,
                    headers=headers,
                    cookies=cookies,
                    allow_redirects=redirects,
                    proxy=self._proxy,
                    proxy_auth=self._proxy_auth,
                    params=params,
                    json=json,
                    data=data,
                    ssl=ssl.create_default_context(cafile=certifi.where()))
                yield r
            else:
                    t=await self._httpx_funct_async(  
                         method,
                        follow_redirects=redirects,
                        url=url,
                        cookies=cookies,
                        headers=headers,
                        json=json,
                        params=params)
                    yield t
        except Exception as e:
            raise e
        finally:
            self._sem.release()


    async def _httpx_funct_async(self,*args,**kwargs):
        t = await    self._session.request(*args,**kwargs)
        t.json_ = lambda: self.factoryasync(t.json)
        t.text_ = lambda: self.factoryasync(t.text)
        t.status = t.status_code
        t.iter_chunked = t.aiter_bytes
        return t

    def _httpx_funct(self, method, **kwargs):
        t = self._session.request(method.upper(), **kwargs)
        t.ok = not t.is_error
        t.json_ = t.json
        t.text_ = lambda: t.text
        t.status = t.status_code
        t.iter_chunked = t.iter_bytes
        return t

    async def _aio_funct(self,method, *args, **kwargs):
            #public function forces context manager use
            r = await self._session._request(method,*args,**kwargs)
            r.text_ = r.text
            r.json_ = r.json
            r.iter_chunked = r.content.iter_chunked
            return r

    async def factoryasync(self, input):
        if callable(input):
            return input()
        return input

    @property
    def delay(self):
        return self._sem.delay
    @delay.setter
    def delay(self, value):
        self._sem.delay = value