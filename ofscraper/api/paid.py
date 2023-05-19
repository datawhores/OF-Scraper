r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
from urllib.request import urlopen
from rich.console import Console
import httpx
import logging
import ofscraper.utils.auth as auth
import ofscraper.constants as constants
paid_content_list_name = 'list'
log=logging.getLogger(__package__)
console=Console()
















def scrape_paid(username):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list."""
    media_to_download = []
    offset = 0
    hasMore = True
    headers = auth.make_headers(auth.read_auth())
    count=1
    with httpx.Client(http2=True, headers=headers, follow_redirects=True) as c:
        while hasMore:
            auth.add_cookies(c)
            url = constants.purchased_contentEP.format(offset,username)
            offset += 10
            c.headers.update(auth.create_sign(url, headers))
            r = c.get(url, timeout=None)
            if not r.is_error:
                log.info(f"Scraping paid content, Scraping isn't frozen. It takes time.\nScraped Page: {count}")
                if "hasMore" in r.json():
                    hasMore = r.json()['hasMore']
                    count=count+1
                media_to_download.extend(list(filter(lambda x:isinstance(x,list),r.json().values()))[0])
    log.debug(f"[bold]Paid Post count without Dupes[/bold] {len(media_to_download)} found")
    return media_to_download







