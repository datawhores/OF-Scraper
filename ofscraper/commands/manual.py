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
import ofscraper.api.highlights as highlights_
import ofscraper.constants as constants


log = logging.getLogger(__package__)


def manual_download(urls=None):
    media_dict=get_media_from_urls(urls)
    log.debug(f"Media dict length {len(list(media_dict.values()))}")
    for value in media_dict.values():
        if len(value)==0:
            continue
        model_id =value[0].post.model_id
        username=value[0].post.username
        log.info(f"Downloading individual for {username}")
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
    args.dupe=True
    args_.changeargs(args)
    user_name_dict={}
    id_dict={}
    with httpx.Client(http2=True) as c:
        for url in url_helper(urls):
            response=get_info(url)
            model=response[0]
            postid=response[1]
            type=response[2]
            if type=="post":
                model_id=user_name_dict.get(model) or profile.get_id( model)
                user_name_dict[model]=model_id
                id_dict[model_id]=id_dict.get(model_id,[])+[timeline.get_individual_post(postid,client=c)]
            elif type=="msg":
                model_id=model
                id_dict[model_id]=id_dict.get(model_id,[])+[messages_.get_individual_post(model_id,postid,client=c)]
            elif type=="msg2":
                model_id=user_name_dict.get(model) or profile.get_id( model)
                id_dict[model_id]=id_dict.get(model_id,[])+[messages_.get_individual_post(model_id,postid,client=c)]
            elif type=="unknown":
                data=unknown_type_helper(postid,c) or {}
                model_id=data.get("author",{}).get("id")
                id_dict[model_id]=id_dict.get(model_id,[])+[data]
            elif type=="highlights":
                data=highlights_.get_individual_highlight(postid,c) or {}
                model_id=data.get("userId")
                id_dict[model_id]=id_dict.get(model_id,[])+[data]
                #special case
                return get_all_media(id_dict,"highlights")
            elif type=="stories":
                data=highlights_.get_individual_stories(postid,c) or {}
                model_id=data.get("userId")
                id_dict[model_id]=id_dict.get(model_id,[])+[data]
                #special case
                return get_all_media(id_dict,"stories")

            else:
                continue
                

    return get_all_media(id_dict)

def unknown_type_helper(postid,client):
    # try to get post by id
    return timeline.get_individual_post(postid,client)
            

    

def get_all_media(id_dict,inputtype=None):
    media_dict={}

    for model_id,value in  id_dict.items():
        temp = []
        user_name = profile.scrape_profile( model_id)['username']
        posts_array=list(map(lambda x:posts_.Post(
        x, model_id, user_name,responsetype=inputtype), value))
        [temp.extend(ele.media) for ele in posts_array]
        media_dict[model_id]=temp
   
   
    return media_dict

    

def get_info(url):
    search1=re.search(f"chats/chat/({constants.NUMBER_REGEX}+)/.*?({constants.NUMBER_REGEX}+)",url)
    search2=re.search(f"/({constants.NUMBER_REGEX}+)/stories/highlights",url)
    search3=re.search(f"/({constants.NUMBER_REGEX}+)/stories",url)
    search4=re.search(f"chats/({constants.USERNAME_REGEX}+)/.*?id=({constants.NUMBER_REGEX}+)",url)
    search5=re.search(f"/({constants.NUMBER_REGEX}+)/({constants.USERNAME_REGEX}+)",url)
    search6=re.search(f"^{constants.NUMBER_REGEX}+$",url)
  #model,postid,type

    if search1:
        return search1.group(1),search1.group(2),"msg"
    elif search2:
        return None,search2.group(1),"highlights"
    elif search3:
        return None,search3.group(1),"stories"


    elif search4:
        return search4.group(1),search4.group(2),"msg2"

    elif search5:
        return search5.group(2),search5.group(1),"post"
    elif search6:
        return None,search6.group(0),"unknown"


    return None,None,None


def url_helper(urls):
    args = args_.getargs()
    args=vars(args)
    out = []
    out.extend(args.get("file",[]) or [])
    out.extend(args.get("url",[]) or [])
    out.extend(urls or [])
    return map(lambda x: x.strip(), out)


    