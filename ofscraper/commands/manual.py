import re
import logging
import asyncio
import httpx
import ofscraper.utils.args as args_
import ofscraper.api.timeline as timeline
import ofscraper.api.profile as profile
import ofscraper.api.timeline as timeline
import ofscraper.utils.auth as auth
import ofscraper.api.posts as posts_
import ofscraper.db.operations as operations
import ofscraper.utils.download as download
import ofscraper.api.messages as messages_


log = logging.getLogger(__package__)

args = args_.getargs()
def manual_download():
    headers = auth.make_headers(auth.read_auth())
    args.dupe=True
    args_.changeargs(args)
    user_name_dict={}
    id_dict={}
    with httpx.Client(http2=True, headers=headers) as c:
        for url in url_helper():
            response=get_info(url)
            if None in response:
                continue
            model=response[0]
            postid=response[1]
            type=response[2]
            if type=="post":
                model_id=user_name_dict.get(model) or profile.get_id(headers, model)
                user_name_dict[model]=model_id
                id_dict[model_id]=id_dict.get(model_id,[])+[timeline.get_individual_post(postid,client=c)]
            elif type=="msg":
                model_id=model
                id_dict[model_id]=id_dict.get(model_id,[])+[messages_.get_individual_post(model_id,postid,client=c)]


    media_dict=get_all_media(id_dict)
    for value in media_dict.values():
        model_id =value[0].post.model_id
        username=value[0].post.username
        log.info(f"Downloading Invidual Post for {username}")
        operations.create_tables(model_id,username)
        operations.write_profile_table(model_id,username)
        asyncio.run(download.process_dicts(
        username,
        model_id,
        value,
        ))  
            

    

def get_all_media(id_dict):
    media_dict={}
    headers = auth.make_headers(auth.read_auth())

    for model_id,value in  id_dict.items():
        temp = []
        user_name = profile.scrape_profile(headers, model_id)['username']
        posts_array=list(map(lambda x:posts_.Post(
        x, model_id, user_name), value))
        [temp.extend(ele.all_media) for ele in posts_array]
        media_dict[model_id]=temp
   
   
    return media_dict

    
    

def get_info(url):
    search1=re.search("chat/([0-9]+)/.*?([0-9]+)",url)
    search2=re.search("/([0-9]+)/([a-z-]+)",url)

    if search1:
        return search1.group(1),search1.group(2),"msg"
    elif search2:
        return search2.group(2),search2.group(1),"post"

    return None,None,None


def url_helper():
    out = []
    out.extend(args.file or [])
    out.extend(args.url or [])
    return map(lambda x: x.strip(), out)
