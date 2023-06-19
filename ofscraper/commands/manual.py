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


def manual_download(urls=None):
    media_dict=get_media_from_urls(urls)
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
    log.info(f"Finished")

def get_media_from_urls(urls):
    args = args_.getargs()
    headers = auth.make_headers(auth.read_auth())
    args.dupe=True
    args_.changeargs(args)
    user_name_dict={}
    id_dict={}
    with httpx.Client(http2=True, headers=headers) as c:
        for url in url_helper(urls):
            response=get_info(url)
            model=response[0]
            postid=response[1]
            type=response[2]
            data=timeline.get_individual_post(postid,client=c) if (type=="unknown" or type=="post") else None
            data = data or messages_.get_individual_post(model_id,postid,client=c) if type=="msg" else None
            data = data or messages_.get_individual_post(model_id,postid,client=c) if type=="paid" else None
            if type=="post":
                model_id=user_name_dict.get(model) or profile.get_id(headers, model)
                user_name_dict[model]=model_id
                id_dict[model_id]=id_dict.get(model_id,[])+[timeline.get_individual_post(postid,client=c)]
            elif type=="msg":
                model_id=model
                id_dict[model_id]=id_dict.get(model_id,[])+[messages_.get_individual_post(model_id,postid,client=c)]
                id_dict[model_id]=id_dict.get(model_id,[])+[timeline.get_individual_post(postid,client=c)]
            elif type=="msg2":
                model_id=user_name_dict.get(model) or profile.get_id(headers, model)
                id_dict[model_id]=id_dict.get(model_id,[])+[messages_.get_individual_post(model_id,postid,client=c)]
            elif type=="unknown":
                unknown_type_helper(postid,c)
            else:
                continue
                

    return get_all_media(id_dict)

def unknown_type_helper(postid,client):
    # try to get post by id
    data=timeline.get_individual_post(postid,client)
    return data
            

    

def get_all_media(id_dict):
    media_dict={}
    headers = auth.make_headers(auth.read_auth())

    for model_id,value in  id_dict.items():
        temp = []
        user_name = profile.scrape_profile(headers, model_id)['username']
        posts_array=list(map(lambda x:posts_.Post(
        x, model_id, user_name), value))
        [temp.extend(ele.media) for ele in posts_array]
        media_dict[model_id]=temp
   
   
    return media_dict

    
    

def get_info(url):
    search1=re.search("chat/([0-9]+)/.*?([0-9]+)",url)
    search2=re.search("/([0-9]+)/([a-z-_.]+)",url)
    search3=re.search("chat/([a-z-\._]+)/.*?([0-9]+)",url)
    search4=re.search("^[0-9]+$",url)


    if search1:
        return search1.group(1),search1.group(2),"msg"
    elif search2:
        return search2.group(2),search2.group(1),"post"
    
    elif search3:
        return search3.group(1),search3.group(2),"msg2"
    elif search4:
        return None,search4.group(0),"unknown"

    return None,None,None


def url_helper(urls):
    args = args_.getargs()
    out = []
    out.extend(args.file or [])
    out.extend(args.url or [])
    out.extend(urls or [])
    return map(lambda x: x.strip(), out)


    