import asyncio
import contextvars
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import logging
import httpx
from tenacity import retry,stop_after_attempt,wait_random

import ofscraper.constants as constants
from ..utils import auth
log=logging.getLogger(__package__)
sem = semaphoreDelayed(1)
attempt = contextvars.ContextVar("attempt")

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_pinned_posts(headers, model_id,timestamp=0) -> list:
        
    async with sem:
        sem.acquire()
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            ep = constants.timelinePinnedNextEP if timestamp else constants.timelinePinnedEP
            url = ep.format(model_id, timestamp)
            # url = timelinePinnedEP.format(model_id)
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))

            r = await c.get(url, timeout=None)
            sem.release()
            if not r.is_error:
                return r.json()['list']
            r.raise_for_status()
            log.debug(f"[bold]pinned request status code:[/bold]{r.status_code}")
            log.debug(f"[bold]pinned response:[/bold] {r.content.decode()}")

def get_pinned_post(headers,model_id):
    return asyncio.run(scrape_pinned_posts(headers,model_id)) or []
   