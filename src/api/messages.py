r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import httpx
from tenacity import retry,stop_after_attempt,wait_random

from ..constants import messagesEP, messagesNextEP
from ..utils import auth

@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
def scrape_messages(headers, user_id, message_id=0) -> list:
    ep = messagesNextEP if message_id else messagesEP
    url = ep.format(user_id, message_id)

    with httpx.Client(http2=True, headers=headers) as c:
        auth.add_cookies(c)
        c.headers.update(auth.create_sign(url, headers))

        r = c.get(url, timeout=None)
        if not r.is_error:
            messages = r.json()['list']
            if not messages:
                return messages
            messages += scrape_messages(headers, user_id, messages[-1]['id'])
            return messages
        r.raise_for_status()


def parse_messages(messages: list, user_id):
    messages_with_media =list(filter(lambda message:message['fromUser']['id'] == user_id and message['media'] ,messages))

    messages_urls = []
    for message in messages_with_media:
        for count,media in enumerate(list(filter(lambda x:x["canView"]==True,message["media"]))):
                messages_urls.append({"url":media["source"]["source"],"id":media["id"],"count":count+1,"mediatype":media["type"],
                    "text":message["text"],'responsetype':"messages","date":message["createdAt"],"data":message})

    return messages_urls
    
