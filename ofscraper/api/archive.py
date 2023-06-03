r"""
                                                             
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
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

def get_archive_post(headers,model_id):
    return asyncio.run(scrape_archived_posts(headers,model_id)) or []
   

@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_archived_posts(headers, model_id, timestamp=0) -> list:
    ep = constants.archivedNextEP if timestamp else constants.archivedEP
    url = ep.format(model_id, timestamp)
    async with sem:
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))

            r = await c.get(url, timeout=None)
            if not r.is_error:
                posts = r.json()['list']
                if not posts:
                    return posts
                posts += await scrape_archived_posts(
                    headers, model_id, posts[-1]['postedAtPrecise'])
                return posts
            r.raise_for_status()
            log.debug(f"[bold]archived request status code:[/bold]{r.status_code}")
            log.debug(f"[bold]archived response:[/bold] {r.content.decode()}")
