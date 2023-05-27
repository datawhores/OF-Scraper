import logging
import re
import httpx
import ofscraper.utils.args as args_
import ofscraper.utils.console as console
import ofscraper.db.operations as operations
import ofscraper.api.profile as profile
import ofscraper.utils.auth as auth
import ofscraper.api.timeline as timeline
log=logging.getLogger(__package__)
args=args_.getargs()

def main():
    user_dict=create_userpost_dict()
    post_checker(user_dict)
   
   
def post_checker(user_dict):
    headers = auth.make_headers(auth.read_auth())
    client=httpx.Client(http2=True, headers=headers)
    for user_name in user_dict.keys():
        model_id = profile.get_id(headers, user_name)
        posts=user_dict[user_name].get("posts")
        downloaded=set(operations.get_media_ids(model_id,user_name))
        for ele in posts:
            media=list(map(lambda x:x["id"],(timeline.get_individual_post(ele,client=client) or {'media':[]})["media"]))
            if len(list(filter(lambda x:x not in downloaded ,media)))>0:
                    console.shared_console.print(f"https://onlyfans.com/{ele}/{user_name} has media not in database")
            else: 
                console.shared_console.print(f"https://onlyfans.com/{ele}/{user_name} all media already downloaded")




def create_userpost_dict():
    outdict={}
    for ele in args.url:
        if re.search("onlyfans.com/[0-9]+/[a-z]+",ele):
            name_match=re.search("/([a-z]+$)",ele)
            num_match=re.search("/([0-9]+)",ele)
            if name_match and num_match:
                if not outdict.get(name_match.group(1)):
                    outdict[name_match.group(1)]={}
                outdict[name_match.group(1)]["posts"]=outdict[name_match.group(1)].get("posts") or set()
                outdict[name_match.group(1)]["posts"].add(num_match.group(1))
    return outdict





