import asyncio
import contextlib
import logging
import threading
import time
import traceback
import sys # For sys.exc_info() in stream context manager

import arrow
import httpx
import tenacity
from tenacity import AsyncRetrying, Retrying, retry_if_not_exception_type

# Assuming these utility modules are available and function as expected
# You might need to adjust imports based on your project structure
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.constants as constants
from ofscraper.utils.auth.utils.warning.print import print_auth_warning

# Action constants
TOO_MANY = "too_many"
AUTH = "auth"
FORCED_NEW = "get_new_sign"  # Implies SIGN
SIGN = "get_sign"
COOKIES = "get_cookies_str"
HEADERS = "create_header" # General header creation trigger
FOUR_OH_FOUR_OK = "404_OK" # New action to treat 404 as non-error

log = logging.getLogger("shared") 


# --- Error Type Checking ---
def is_httpx_status_error(exception, *status_codes):
    """Checks if the exception is an httpx.HTTPStatusError with specific status codes."""
    return (
        isinstance(exception, httpx.HTTPStatusError)
        and exception.response.status_code in status_codes
    )

# --- Rate Limit and Error Handling Logic ---
class SessionSleep:
    """Manages sleep intervals, especially for rate limiting."""
    def __init__(self, initial_sleep=None, increase_time_diff=None):
        self._sleep = None
        self._initial_sleep = initial_sleep if initial_sleep is not None else constants.getattr("SESSION_SLEEP_INIT", 5) # Default 5s
        self._last_increase_time = arrow.now()
        self._min_time_between_increases = (
            increase_time_diff
            if increase_time_diff is not None
            else constants.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF", 60) # Default 60s
        )
        self._lock = threading.Lock() # For sync version
        self._async_lock = asyncio.Lock() # For async version
        self.max_sleep = constants.getattr("SESSION_MAX_SLEEP", 300) # Max sleep 5 minutes

    def reset_sleep(self):
        """Resets the sleep duration to its initial value."""
        with self._lock: # Ensure thread safety for reset
            self._sleep = self._initial_sleep
            self._last_increase_time = arrow.now()
        log.debug("SessionSleep: Sleep reset to initial.")


    def _increase_sleep_duration(self):
        """Increases the sleep duration, respecting max_sleep."""
        if not self._sleep:
            self._sleep = self._initial_sleep
            log.debug(f"SessionSleep: Initialized sleep to {self._sleep}s.")
        elif arrow.now().float_timestamp - self._last_increase_time.float_timestamp < self._min_time_between_increases:
            log.debug(f"SessionSleep: Not increasing sleep ({self._sleep}s). Last increase was too recent.")
        else:
            self._sleep = min(self._sleep * 2, self.max_sleep)
            log.debug(f"SessionSleep: Increased sleep to {self._sleep}s.")
        self._last_increase_time = arrow.now()

    def toomany_req(self):
        """Handles 'too many requests' synchronously, increasing sleep time."""
        with self._lock:
            self._increase_sleep_duration()
        return self._sleep

    async def async_toomany_req(self):
        """Handles 'too many requests' asynchronously, increasing sleep time."""
        async with self._async_lock:
            self._increase_sleep_duration()
        return self._sleep

    def do_sleep(self):
        """Performs a synchronous sleep if a sleep duration is set."""
        current_sleep = self._sleep # Read it once
        if current_sleep and current_sleep > 0:
            log.debug(f"SessionSleep: Sleeping for {current_sleep}s due to previous rate limit or error.")
            time.sleep(current_sleep)

    async def async_do_sleep(self):
        """Performs an asynchronous sleep if a sleep duration is set."""
        current_sleep = self._sleep # Read it once
        if current_sleep and current_sleep > 0:
            log.debug(f"SessionSleep: Async sleeping for {current_sleep}s due to previous rate limit or error.")
            await asyncio.sleep(current_sleep)

    @property
    def current_sleep_duration(self):
        return self._sleep

class BaseCustomClient:
    def __init__(self, *,
                 retries=None, wait_min=None, wait_max=None,
                 connect_timeout=None, read_timeout=None, pool_timeout=None, total_timeout=None,
                 proxy=None, limits=None, log_level=None, **kwargs): # Added log_level
        
        # Initialize logging for this instance
        self.log = logging.getLogger(self.__class__.__name__)
        if log_level is not None: # Allow per-instance log level override
            self.log.setLevel(log_level)

        # Default settings from constants
        self._retries = retries if retries is not None else constants.getattr("OF_NUM_RETRIES_SESSION_DEFAULT", 5)
        self._wait_min = wait_min if wait_min is not None else constants.getattr("OF_MIN_WAIT_SESSION_DEFAULT", 1)
        self._wait_max = wait_max if wait_max is not None else constants.getattr("OF_MAX_WAIT_SESSION_DEFAULT", 5)
        
        # Default timeouts
        self._default_connect_timeout = connect_timeout if connect_timeout is not None else constants.getattr("CONNECT_TIMEOUT", 10)
        self._default_read_timeout = read_timeout if read_timeout is not None else constants.getattr("READ_TIMEOUT", 30)
        self._default_pool_timeout = pool_timeout if pool_timeout is not None else constants.getattr("POOL_CONNECT_TIMEOUT", 10)
        self._default_total_timeout = total_timeout if total_timeout is not None else constants.getattr("TOTAL_TIMEOUT", 60)

        self.sleeper = SessionSleep(
            initial_sleep=constants.getattr("SESSION_SLEEP_INIT", 0), # Start with 0 unless specified
            increase_time_diff=constants.getattr("SESSION_SLEEP_INCREASE_TIME_DIFF", 60)
        )
        
        self.proxy = proxy or constants.getattr("PROXY")
        
        # HTTPX client limits
        self.limits_config = limits or httpx.Limits(
            max_keepalive_connections=constants.getattr("KEEP_ALIVE", 20),
            max_connections=constants.getattr("MAX_CONNECTIONS", 100),
            keepalive_expiry=constants.getattr("KEEP_ALIVE_EXP", 60.0),
        )
        
        # Store other httpx passthrough kwargs
        self._httpx_kwargs = kwargs


    def _prepare_headers_and_cookies(self, url, current_headers, current_cookies_dict, actions):
        """Prepares headers and cookies based on actions."""
        headers_to_use = (current_headers or {}).copy()
        cookies_to_use = (current_cookies_dict or {}).copy()

        if HEADERS in actions or SIGN in actions or FORCED_NEW in actions:
            # auth_requests.make_headers() should return a dict
            headers_to_use.update(auth_requests.make_headers())
            if SIGN in actions or FORCED_NEW in actions:
                # auth_requests.create_sign modifies headers in place
                auth_requests.create_sign(url, headers_to_use)
        
        if COOKIES in actions:
            # auth_requests.add_cookies() should return a dict or httpx.Cookies
            # httpx.Client/AsyncClient can take a dict for cookies
            new_cookies = auth_requests.add_cookies()
            if isinstance(new_cookies, httpx.Cookies): # If it's a CookieJar instance
                # Convert to dict or ensure compatibility; httpx handles CookieJar instances.
                # For simplicity, if it returns a dict, merge it.
                # If it returns a CookieJar, httpx will use it. Here we assume it's a dict to merge.
                # If add_cookies returns a full CookieJar, it might be better to pass it directly.
                # For now, let's assume it returns a dict to be merged.
                if isinstance(new_cookies, dict):
                     cookies_to_use.update(new_cookies)
                else: # If it's a CookieJar, httpx will handle it.
                    cookies_to_use = new_cookies # Replace, don't update
            elif isinstance(new_cookies, dict):
                 cookies_to_use.update(new_cookies)


        return headers_to_use, cookies_to_use

    def _get_timeout_config(self, per_request_timeouts=None):
        """Constructs an httpx.Timeout object for a request."""
        timeouts = per_request_timeouts or {}
        return httpx.Timeout(
            timeouts.get("total", self._default_total_timeout),
            connect=timeouts.get("connect", self._default_connect_timeout),
            read=timeouts.get("read", self._default_read_timeout),
            pool=timeouts.get("pool", self._default_pool_timeout)
        )

    def _log_attempt(self, retry_state):
        """Logs retry attempts."""
        if retry_state.attempt_number > 1:
            self.log.debug(f"Retrying request (attempt {retry_state.attempt_number})...")
            if retry_state.outcome:
                 self.log.debug(f"Previous attempt failed with: {retry_state.outcome.exception()}")


    def _log_error_response(self, response, is_async=False, is_stream=False):
        """Logs details of an error response."""
        self.log.warning(f"Request failed: {response.request.method} {response.url} - Status: {response.status_code}")
        # For streams, reading text might consume the stream or block. Be cautious.
        # For async, response.text needs to be awaited.
        # This part needs careful handling if we want to log response body for errors.
        # For now, just log status and headers.
        self.log.debug(f"Error Response Headers: {dict(response.headers)}")
        # Add more details if safe and needed, e.g. response.text if not a stream and small
        # if not is_stream:
        #     try:
        #         content = response.text if not is_async else await response.text
        #         self.log.debug(f"Error Response Body (first 500 chars): {content[:500]}")
        #     except Exception as e:
        #         self.log.debug(f"Could not read error response body: {e}")


    def _handle_exception_actions(self, exc, actions, is_async=False):
        """Handles actions based on exceptions (e.g., 400, 429)."""
        # 400 error code handling (e.g., auth issues)
        if AUTH in actions and is_httpx_status_error(exc, 400):
            self.log.warning("Received 400 error, possibly auth-related. Applying specific delay.")
            print_auth_warning() # Assuming this prints a user-friendly message
            if is_async:
                # Schedule the sleep without blocking the retryer's async flow directly
                # This is tricky. asyncio.sleep(8) here would pause the retry logic.
                # The original async_check_400 did asyncio.sleep(8).
                # This means the 8s sleep is part of the attempt's duration *before* tenacity's wait.
                # We'll replicate this behavior.
                # await asyncio.sleep(8) # This needs to be done in the async request method's except block.
                pass # Placeholder: actual sleep will be in the async request method
            else:
                time.sleep(8) # Sync sleep

        # 429 (Too Many Requests) or 504 (Gateway Timeout) handling
        if TOO_MANY in actions and is_httpx_status_error(exc, 429, 504):
            self.log.warning(f"Received {exc.response.status_code} error. Increasing session sleep.")
            if is_async:
                asyncio.create_task(self.sleeper.async_toomany_req()) # Run in background to not block
            else:
                self.sleeper.toomany_req()


# --- Synchronous Custom HTTPX Client ---
class HttpxClient(BaseCustomClient, httpx.Client):
    def __init__(self, *,
                 retries=None, wait_min=None, wait_max=None,
                 connect_timeout=None, read_timeout=None, pool_timeout=None, total_timeout=None,
                 proxy=None, limits=None, log_level=None, **kwargs):
        
        BaseCustomClient.__init__(self, retries=retries, wait_min=wait_min, wait_max=wait_max,
                                  connect_timeout=connect_timeout, read_timeout=read_timeout,
                                  pool_timeout=pool_timeout, total_timeout=total_timeout,
                                  proxy=proxy, limits=limits, log_level=log_level)
        
        httpx.Client.__init__(self, proxy=self.proxy, limits=self.limits_config, http2=True, **self._httpx_kwargs)

    def _adapt_response(self, response, is_stream=False):
        """Adapts httpx.Response for consistent attribute access."""
        response.ok = not response.is_error
        response.json_ = response.json # .json() is a method
        response.text_ = lambda: response.text # .text is a property
        response.status = response.status_code
        response.iter_chunked = response.iter_bytes # .iter_bytes() is a sync iterator
        response.read_ = response.read # .read() is a sync method
        return response

    def request(self, method, url, *, actions=None, per_request_timeouts=None, **kwargs):
        actions = actions or []
        
        retryer = Retrying(
            stop=tenacity.stop_after_attempt(self._retries),
            wait=tenacity.wait_random(min=self._wait_min, max=self._wait_max),
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            before=self._log_attempt,
            reraise=True
        )

        for attempt in retryer:
            with attempt:
                try:
                    self.sleeper.do_sleep() # Sleep if prior rate limit occurred

                    req_headers = kwargs.pop("headers", None)
                    req_cookies = kwargs.pop("cookies", None) # httpx takes dict or CookieJar

                    prepared_headers, prepared_cookies = self._prepare_headers_and_cookies(
                        url, req_headers, req_cookies, actions
                    )
                    
                    timeout_config = self._get_timeout_config(per_request_timeouts)

                    response = super().request(
                        method,
                        url,
                        headers=prepared_headers,
                        cookies=prepared_cookies, # Pass the prepared cookies
                        timeout=timeout_config,
                        **kwargs # Pass through other httpx args
                    )

                    if response.status_code == 404 and FOUR_OH_FOUR_OK not in actions:
                        self.log.debug(f"Received 404 for {url}, treating as non-error based on actions or default.")
                        # Or specific handling, original code had 'pass'
                    elif not response.is_error: # Use httpx's is_error
                        pass # Successful response
                    else: # is_error is True
                        self._log_error_response(response)
                        response.raise_for_status() # Will raise httpx.HTTPStatusError

                    return self._adapt_response(response)

                except Exception as e:
                    self.log.debug(f"Exception during request to {url}: {type(e).__name__} - {e}")
                    self.log.traceback_(traceback.format_exc()) # Assuming log has traceback_ method

                    # Handle specific actions based on the exception
                    if AUTH in actions and is_httpx_status_error(e, 400):
                        self.log.warning("Sync: Received 400 error, possibly auth-related. Applying 8s delay.")
                        print_auth_warning()
                        time.sleep(8)
                    
                    if TOO_MANY in actions and is_httpx_status_error(e, 429, 504):
                        status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else "N/A"
                        self.log.warning(f"Sync: Received {status} error. Increasing session sleep.")
                        self.sleeper.toomany_req()
                    
                    raise # Reraise for tenacity to handle retry

    @contextlib.contextmanager
    def stream(self, method, url, *, actions=None, per_request_timeouts=None, **kwargs):
        actions = actions or []
        
        retryer = Retrying(
            stop=tenacity.stop_after_attempt(self._retries),
            wait=tenacity.wait_random(min=self._wait_min, max=self._wait_max),
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            before=self._log_attempt,
            reraise=True
        )

        # To ensure __exit__ is called on the stream context manager
        active_stream_ctx = None 
        try:
            for attempt in retryer:
                with attempt:
                    current_attempt_stream_ctx = None
                    response_obj = None
                    try:
                        self.sleeper.do_sleep()

                        req_headers = kwargs.pop("headers", None)
                        req_cookies = kwargs.pop("cookies", None)
                        prepared_headers, prepared_cookies = self._prepare_headers_and_cookies(
                            url, req_headers, req_cookies, actions
                        )
                        timeout_config = self._get_timeout_config(per_request_timeouts)

                        # super().stream returns a context manager
                        current_attempt_stream_ctx = super().stream(
                            method, url, headers=prepared_headers, cookies=prepared_cookies,
                            timeout=timeout_config, **kwargs
                        )
                        
                        response_obj = current_attempt_stream_ctx.__enter__()
                        active_stream_ctx = current_attempt_stream_ctx # Mark for potential exit in outer finally

                        if response_obj.status_code == 404 and FOUR_OH_FOUR_OK not in actions:
                             self.log.debug(f"Stream: Received 404 for {url}, treating as non-error.")
                        elif not response_obj.is_error:
                            pass # Successful stream opening
                        else:
                            self._log_error_response(response_obj, is_stream=True)
                            response_obj.raise_for_status()

                        yield self._adapt_response(response_obj, is_stream=True)
                        return # Successful yield, exit generator and retry loop

                    except Exception as e:
                        self.log.debug(f"Exception during stream to {url} (attempt): {type(e).__name__} - {e}")
                        self.log.traceback_(traceback.format_exc())
                        
                        # If stream was opened in this attempt, ensure it's closed before retry
                        if current_attempt_stream_ctx and response_obj: # __enter__ was successful
                            current_attempt_stream_ctx.__exit__(type(e), e, e.__traceback__)
                            active_stream_ctx = None # It's closed for this attempt

                        if AUTH in actions and is_httpx_status_error(e, 400):
                            self.log.warning("Stream: Received 400 error. Applying 8s delay.")
                            print_auth_warning()
                            time.sleep(8)
                        if TOO_MANY in actions and is_httpx_status_error(e, 429, 504):
                            status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else "N/A"
                            self.log.warning(f"Stream: Received {status} error. Increasing session sleep.")
                            self.sleeper.toomany_req()
                        raise e
            # If loop finishes, retries exhausted. Tenacity re-raises.
        finally:
            # Ensures the stream from the last successful __enter__ (even if yield failed) is closed.
            if active_stream_ctx:
                exc_type, exc_val, exc_tb = sys.exc_info()
                # Filter out GeneratorExit if it's a normal exit from the context manager
                if exc_type is GeneratorExit:
                    active_stream_ctx.__exit__(None,None,None)
                else:
                    active_stream_ctx.__exit__(exc_type, exc_val, exc_tb)


# --- Asynchronous Custom HTTPX Client ---
class HttpxAsyncClient(BaseCustomClient, httpx.AsyncClient):
    def __init__(self, *,
                 retries=None, wait_min=None, wait_max=None, wait_min_exponential=None, wait_max_exponential=None, # Exponential for async
                 connect_timeout=None, read_timeout=None, pool_timeout=None, total_timeout=None,
                 proxy=None, limits=None, sem_count=None, log_level=None, **kwargs):

        BaseCustomClient.__init__(self, retries=retries, wait_min=wait_min, wait_max=wait_max,
                                  connect_timeout=connect_timeout, read_timeout=read_timeout,
                                  pool_timeout=pool_timeout, total_timeout=total_timeout,
                                  proxy=proxy, limits=limits, log_level=log_level)
        
        httpx.AsyncClient.__init__(self, proxy=self.proxy, limits=self.limits_config, http2=True, **self._httpx_kwargs)

        self._wait_min_exp = wait_min_exponential or constants.getattr("OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT", 1)
        self._wait_max_exp = wait_max_exponential or constants.getattr("OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT", 10)
        
        # Semaphore for controlling concurrency in async requests
        self._sem = asyncio.BoundedSemaphore(sem_count or constants.getattr("SESSION_MANAGER_ASYNC_SEM_DEFAULT", 100))


    async def _adapt_response_async(self, response, is_stream=False):
        """Adapts httpx.Response for consistent async attribute access."""
        response.ok = not response.is_error
        
        # .json() is an async method
        response.json_ = response.json 
        
        # .text is an async property, effectively await response.text
        # To make response.text_() work like original:
        async def text_getter():
            return await response.text
        response.text_ = text_getter
            
        response.status = response.status_code
        # .aiter_bytes() is an async iterator
        response.iter_chunked = response.aiter_bytes 
        # .aread() is an async method
        response.read_ = response.aread 
        return response

    async def request(self, method, url, *, actions=None, per_request_timeouts=None, **kwargs):
        actions = actions or []
        
        # Using a combined wait strategy: random + exponential backoff for async
        combined_wait = tenacity.wait_combine(
            tenacity.wait_random(min=self._wait_min, max=self._wait_max),
            tenacity.wait_exponential(min=self._wait_min_exp, max=self._wait_max_exp)
        )

        retryer = AsyncRetrying(
            stop=tenacity.stop_after_attempt(self._retries),
            wait=combined_wait,
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            before=self._log_attempt, # Tenacity will await if _log_attempt is async, or run sync
            reraise=True
        )

        await self._sem.acquire()
        try:
            async for attempt in retryer: # Use `async for` with AsyncRetrying
                with attempt: # Tenacity's attempt context
                    try:
                        await self.sleeper.async_do_sleep()

                        req_headers = kwargs.pop("headers", None)
                        req_cookies = kwargs.pop("cookies", None)
                        prepared_headers, prepared_cookies = self._prepare_headers_and_cookies(
                            url, req_headers, req_cookies, actions
                        )
                        timeout_config = self._get_timeout_config(per_request_timeouts)

                        response = await super().request(
                            method,
                            url,
                            headers=prepared_headers,
                            cookies=prepared_cookies,
                            timeout=timeout_config,
                            **kwargs
                        )

                        if response.status_code == 404 and FOUR_OH_FOUR_OK not in actions:
                            self.log.debug(f"Async: Received 404 for {url}, non-error.")
                        elif not response.is_error:
                            pass
                        else:
                            await self._log_error_response_async(response) # Make an async version
                            response.raise_for_status()
                        
                        return await self._adapt_response_async(response)

                    except Exception as e:
                        self.log.debug(f"Async Exception during request to {url}: {type(e).__name__} - {e}")
                        self.log.traceback_(traceback.format_exc())

                        if AUTH in actions and is_httpx_status_error(e, 400):
                            self.log.warning("Async: Received 400 error. Applying 8s delay.")
                            print_auth_warning()
                            await asyncio.sleep(8) # Perform async sleep here
                        
                        if TOO_MANY in actions and is_httpx_status_error(e, 429, 504):
                            status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else "N/A"
                            self.log.warning(f"Async: Received {status} error. Increasing session sleep.")
                            await self.sleeper.async_toomany_req()
                        raise
        finally:
            self._sem.release()

    @contextlib.asynccontextmanager
    async def stream(self, method, url, *, actions=None, per_request_timeouts=None, **kwargs):
        actions = actions or []
        combined_wait = tenacity.wait_combine(
            tenacity.wait_random(min=self._wait_min, max=self._wait_max),
            tenacity.wait_exponential(min=self._wait_min_exp, max=self._wait_max_exp)
        )
        retryer = AsyncRetrying(
            stop=tenacity.stop_after_attempt(self._retries),
            wait=combined_wait,
            retry=retry_if_not_exception_type(KeyboardInterrupt),
            before=self._log_attempt,
            reraise=True
        )

        active_stream_ctx = None
        await self._sem.acquire()
        try:
            async for attempt in retryer:
                with attempt:
                    current_attempt_stream_ctx = None
                    response_obj = None
                    try:
                        await self.sleeper.async_do_sleep()

                        req_headers = kwargs.pop("headers", None)
                        req_cookies = kwargs.pop("cookies", None)
                        prepared_headers, prepared_cookies = self._prepare_headers_and_cookies(
                            url, req_headers, req_cookies, actions
                        )
                        timeout_config = self._get_timeout_config(per_request_timeouts)
                        
                        current_attempt_stream_ctx = super().stream( # This is a sync method returning async_cm
                            method, url, headers=prepared_headers, cookies=prepared_cookies,
                            timeout=timeout_config, **kwargs
                        )
                        
                        response_obj = await current_attempt_stream_ctx.__aenter__()
                        active_stream_ctx = current_attempt_stream_ctx

                        if response_obj.status_code == 404 and FOUR_OH_FOUR_OK not in actions:
                            self.log.debug(f"Async Stream: Received 404 for {url}, non-error.")
                        elif not response_obj.is_error:
                            pass
                        else:
                            await self._log_error_response_async(response_obj, is_stream=True)
                            response_obj.raise_for_status()

                        yield await self._adapt_response_async(response_obj, is_stream=True)
                        return # Successful yield

                    except Exception as e:
                        self.log.debug(f"Async Exception during stream to {url} (attempt): {type(e).__name__} - {e}")
                        self.log.traceback_(traceback.format_exc())

                        if current_attempt_stream_ctx and response_obj: # __aenter__ was successful
                            await current_attempt_stream_ctx.__aexit__(type(e), e, e.__traceback__)
                            active_stream_ctx = None
                        
                        if AUTH in actions and is_httpx_status_error(e, 400):
                            self.log.warning("Async Stream: Received 400 error. Applying 8s delay.")
                            print_auth_warning()
                            await asyncio.sleep(8)
                        if TOO_MANY in actions and is_httpx_status_error(e, 429, 504):
                            status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else "N/A"
                            self.log.warning(f"Async Stream: Received {status} error. Increasing session sleep.")
                            await self.sleeper.async_toomany_req()
                        raise e
        finally:
            if active_stream_ctx:
                exc_type, exc_val, exc_tb = sys.exc_info()
                if exc_type is GeneratorExit: # Normal exit from async context manager
                     await active_stream_ctx.__aexit__(None,None,None)
                else: # Exiting due to an exception
                    await active_stream_ctx.__aexit__(exc_type, exc_val, exc_tb)
            self._sem.release()

    # Helper for async error logging (if response body is needed)
    async def _log_error_response_async(self, response, is_stream=False):
        self.log.warning(f"Async Request failed: {response.request.method} {response.url} - Status: {response.status_code}")
        self.log.debug(f"Async Error Response Headers: {dict(response.headers)}")
        # if not is_stream:
        #     try:
        #         content = await response.text
        #         self.log.debug(f"Async Error Response Body (first 500 chars): {content[:500]}")
        #     except Exception as e:
        #         self.log.debug(f"Could not read async error response body: {e}")



