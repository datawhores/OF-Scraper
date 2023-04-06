r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import time
import httpx
from tenacity import retry,stop_after_attempt,wait_random
from tqdm.asyncio import tqdm
import arrow
global sem
sem = asyncio.Semaphore(8)
from ..constants import messagesEP, messagesNextEP
from ..utils import auth
from ..db.operations import read_messages_response


async def get_messages(headers,  model_id,username):
    oldmessages=read_messages_response(model_id,username)
    postedAtArray=list(map(lambda x:x["id"],sorted(oldmessages,key=lambda x:arrow.get(x["createdAt"]).float_timestamp,reverse=True)))
    global tasks
    tasks=[]
    
    #split and interval can't match because of breakpoints
    split=40
    interval=30
    if len(postedAtArray)>split:
        splitArrays=[postedAtArray[i:i+split] for i in range(0, len(postedAtArray), interval)]
        tasks.append(asyncio.create_task(scrape_messages(headers,model_id)))
        tasks.extend(list(map(lambda x:asyncio.create_task(scrape_messages(headers,model_id,message_id=x[0])),splitArrays[1:-1])))
        tasks.append(asyncio.create_task(scrape_messages(headers,model_id,message_id=splitArrays[-1][0],recursive=True)))
    else:
        tasks.append(asyncio.create_task(scrape_messages(headers,model_id,recursive=True)))
   
  
    
    
    responseArray=[]
    page_count=0 
    desc = 'Pages Progress: {page_count}'   

    with tqdm(desc=desc.format(page_count=page_count), colour='cyan',position=2) as main_bar:
        while len(tasks)!=0:
                    for coro in asyncio.as_completed(tasks):
                        result=await coro
                        page_count=page_count+1
                        main_bar.set_description(desc.format(page_count=page_count), refresh=False)
                        main_bar.update()
                        responseArray.extend(result)
                    time.sleep(2)
                    tasks=list(filter(lambda x:x.done()==False,tasks))
    unduped=[]
    dupeSet=set()
    for message in responseArray:
        if message["id"] in dupeSet:
            continue
        dupeSet.add(message["id"])
        unduped.append(message)
    return unduped

@retry(stop=stop_after_attempt(5),wait=wait_random(min=5, max=20),reraise=True)   
async def scrape_messages(headers, user_id, message_id=None,recursive=False) -> list:
    ep = messagesNextEP if message_id else messagesEP
    url = ep.format(user_id, message_id)
    async with sem:
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))
            r = await c.get(url, timeout=None)
            if not r.is_error:
                messages = r.json()['list']
                if not messages:
                    return []
                elif len(messages)==0:
                    return messages
                elif not recursive:
                    return messages
                global tasks
                tasks.append(asyncio.create_task(scrape_messages(headers, user_id, recursive=True,message_id=messages[-1]['id'])))
                return messages
            r.raise_for_status()


def parse_messages(messages: list, user_id):
    messages_with_media =list(filter(lambda message:message['fromUser']['id'] == user_id and message['media'] ,messages))

    messages_urls = []
    for message in messages_with_media:
        for count,media in enumerate(list(filter(lambda x:x["canView"]==True,message["media"]))):
                messages_urls.append({"url":media["source"]["source"],"id":media["id"],"count":count+1,"mediatype":media["type"],
        "text":message["text"],'responsetype':"messages","date":message["createdAt"],"value":"free" if message["price"]==0 else "paid","postid":message["id"],"data":message})

    return messages_urls
    
