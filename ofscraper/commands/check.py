import logging
import re
import ofscraper.utils.args as args_
import ofscraper.utils.console as console
import ofscraper.db.operations as operations
import ofscraper.api.profile as profile
import ofscraper.utils.auth as auth




log=logging.getLogger(__package__)
args=args_.getargs()

def main():
    user_dict=create_userpost_dict()
    headers = auth.make_headers(auth.read_auth())

    for key in user_dict.keys():
        model_id = profile.get_id(headers, key)
        posts=user_dict[key].get("posts")
        messages=user_dict[key].get("messages")
        downloaded=set(operations.get_post_ids(model_id,key))
        if posts:
            posts_downloaded=list(filter(lambda x:x in downloaded,posts))
            posts_missing=list(filter(lambda x:x not in downloaded,posts))
            for ele in posts_missing:
                console.shared_console.print(f"https://onlyfans.com/{ele}/{key} was not detected")
            for ele in posts_downloaded:
                            console.shared_console.print(f"https://onlyfans.com/{ele}/{key} this post was already found")



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





