
import asyncio
import contextlib
import ssl
import certifi
import httpx
import aiohttp
import functools
import ofscraper.constants as constants
from ..utils import auth
import ofscraper.utils.config as config_


####
#  This class allows the user to select which backend aiohttp or httpx they want to use
#  httpx has better compatiblilty but is slower
# 
#####


class sessionBuilder:
    def __init__(self,backend=None, set_header=True,set_sign=True,async_param=True,set_cookies=True):
        self._backend=backend or config_.get_backend(config_.read_config())
        self._set_cookies=set_cookies
        self._set_header=set_header
        self._set_sign=set_sign
        self._async=async_param
        
     

    async def __aenter__(self):

        if self._backend=="aio":
            self._obj= aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=constants.API_REEQUEST_TIMEOUT, connect=None,
                      sock_connect=None, sock_read=None),connector = aiohttp.TCPConnector(limit=constants.MAX_SEMAPHORE))
        
        
        elif self._backend=="httpx" and self._async:
            self._obj= httpx.AsyncClient(http2=True,timeout=None)
    
        return self
    

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._obj.__aexit__(exc_type, exc_val, exc_tb)
    

    def __enter__(self):
        if self._backend=="httpx" and not self._async:
            self._obj= httpx.Client(http2=True,timeout=None)
        elif self._backend=="aio":
            raise Exception("aiohttp is async only")
        return self
        
        

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._obj.__exit__(exc_type, exc_val, exc_tb)
   

    def _create_headers(self):
        self._headers= auth.make_headers(auth.read_auth()) if self._set_header else None
        self._create_sign() if self._set_header and self._set_sign else self._headers
        return self._headers

    def _create_sign(self) : 
            if not self._headers:
                 return
            self._headers=auth.create_sign(self._url,self._headers)
            return self._headers   
      
    def _create_cookies(self):
        self._cookies=auth.add_cookies() if self._set_cookies else None
        return self._cookies


    def requests(self,url,req_type="get"):
        self._url=url
        headers=self._create_headers()
        cookies=self._create_cookies()
        if self._backend=="aio":
            self._innerfunct=functools.partial(self._obj.request,req_type,url=self._url,ssl=ssl.create_default_context(cafile=certifi.where()),cookies=cookies,headers=headers)
            self._funct=functools.partial(self._aio_funct_async)

     
            
        elif self._backend=="httpx" and self._async:
            self._innerfunct=functools.partial(self._obj.request,req_type,url=self._url,cookies=cookies,headers=headers)
            self._funct=functools.partial(self._httpx_funct_async)
        elif self._backend=="httpx" and not self._async:
            self._innerfunct=functools.partial(self._obj.request,req_type,url=self._url,cookies=cookies,headers=headers)
            self._funct=functools.partial(self._httpx_funct)
        
        return self._funct
            
            
    # context providers are used to provide access to object before exit
    @contextlib.asynccontextmanager
    async def _httpx_funct_async(self):
        t=await self._innerfunct()
        t.ok=not t.is_error
        t.json_=lambda: self.factoryasync(t.json)
        t.text_=lambda: self.factoryasync(t.text)
        t.status=t.status_code
        yield t
        None

    
    # context providers are used to provide access to object before exit
    @contextlib.contextmanager
    def _httpx_funct(self):
        t=self._innerfunct()
        t.ok=not t.is_error
        t.json_=t.json
        t.text_=lambda: t.text
        t.status=t.status_code
        yield t
        None

    async def factoryasync(self,input):
        if callable(input):
            return input()
        return input
        
    
   

       
        
  
        
    # context providers are used to provide access to object before exit
    @contextlib.asynccontextmanager
    async def _aio_funct_async(self):
        async with self._innerfunct() as r:
            r.text_=r.text
            r.json_=r.json
            yield r
        
    
        None
        
