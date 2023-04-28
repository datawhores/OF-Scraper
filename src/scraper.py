r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
import os
import sys
import platform
import time
import schedule
from contextlib import contextmanager
import threading
import queue
from itertools import chain
import re
from rich.console import Console
import traceback

from .prompts import prompts
console=Console()
from .constants import donateEP
from .api import init, highlights, me, messages, profile, subscriptions, paid, timeline
from .db import operations
from .interaction import like
from .utils import auth, config, download, profiles
import webbrowser
from halo import Halo
from .utils.config import read_config
import src.api.posts as posts_
import src.utils.args as args_
import src.utils.paths as paths
import src.utils.exit as exit



@Halo(text='Getting messages...')
def process_messages(headers, model_id,username):
    messages_ =asyncio.run(messages.get_messages(headers,  model_id,username)) 
    operations.save_messages_response(messages_,model_id,username)
    messages_=list(map(lambda x:posts_.Post(x,model_id,username),messages_))
    for message in messages_:
     operations.write_messages_table(message)
    output=[]
    [ output.extend(message.media) for message in messages_]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

@Halo(text='Getting Paid Content...')
def process_paid_post(headers, model_id,username):
    paid_content=paid.scrape_paid(username)
    paid_content=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="paid"),paid_content))
    for post in paid_content:
        operations.write_post_table(post,model_id,username)
    output=[]
    [output.extend(post.media) for post in paid_content]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

         

@Halo(text='Getting highlights and stories...')
def process_highlights(headers, model_id,username):
    highlights_, stories = highlights.scrape_highlights(headers, model_id)
    highlights_, stories=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="highlights"),highlights_)),\
    list(map(lambda x:posts_.Post(x,model_id,username,responsetype="stories"),stories))
    for post in highlights_:
        operations.write_stories_table(post,model_id,username)
    for post in stories:
        operations.write_stories_table(post,model_id,username)   
    output=[]
    output2=[]
    [ output.extend(highlight.media) for highlight in highlights_]
    [ output2.extend(stories.media) for stories in stories]
    return list(filter(lambda x:isinstance(x,posts_.Media),output)),list(filter(lambda x:isinstance(x,posts_.Media),output2))

     






@Halo(text='Getting timeline media...')
def process_timeline_posts(headers, model_id,username):
    timeline_posts = asyncio.run(timeline.get_timeline_post(headers, model_id,username))
    operations.save_timeline_response(timeline_posts,model_id,username)
    timeline_posts  =list(map(lambda x:posts_.Post(x,model_id,username,"timeline"), timeline_posts ))
    for post in timeline_posts:
        operations.write_post_table(post,model_id,username)
    output=[]
    [output.extend(post.media) for post in  timeline_posts ]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

@Halo(text='Getting archived media...')
def process_archived_posts(headers, model_id,username):
    archived_posts = timeline.get_archive_post(headers, model_id)
    operations.save_archive_response(archived_posts,model_id,username)
    archived_posts =list(map(lambda x:posts_.Post(x,model_id,username),archived_posts ))
    for post in archived_posts:
        operations.write_post_table(post,model_id,username)
    output=[]
    [ output.extend(post.media) for post in archived_posts ]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))




@Halo(text='Getting pinned media...')
def process_pinned_posts(headers, model_id,username):
    pinned_posts = timeline.get_pinned_post(headers, model_id,username)
    operations.save_pinned_response(pinned_posts,model_id,username)
    pinned_posts =list(map(lambda x:posts_.Post(x,model_id,username,"pinned"),pinned_posts ))
    for post in  pinned_posts:
        operations.write_post_table(post,model_id,username)
    output=[]
    [ output.extend(post.media) for post in pinned_posts ]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

def process_profile(headers, username) -> list:
    user_profile = profile.scrape_profile(headers, username)
    urls, info = profile.parse_profile(user_profile)
    profile.print_profile_info(info)
    output=[]
    for ele in enumerate(urls):
        count=ele[0]
        data=ele[1]
        output.append(posts_.Media({"url":data["url"],"type":data["mediatype"]},count,posts_.Post(data,info[2],username,responsetype="profile")))
    return output




def process_areas(headers, ele, model_id) -> list:
    args.posts = list(map(lambda x:x.capitalize(),(args.posts or prompts.areas_prompt())
))
    timeline_posts_dicts  = []
    pinned_post_dict=[]
    archived_posts_dicts  = []
    highlights_dicts  = []
    messages_dicts  = []
    stories_dicts=[]
    purchased_dict=[]
    pinned_post_dict=[]

    username=ele['name']
    profile_dicts  = process_profile(headers,username)

     
    if ('Pinned' in args.posts or 'All' in args.posts) and ele["active"]:
            pinned_post_dict = process_pinned_posts(headers, model_id,username)
    if ('Timeline' in args.posts or 'All' in args.posts) and ele["active"]:
            timeline_posts_dicts = process_timeline_posts(headers, model_id,username)
    if ('Archived' in args.posts or 'All' in args.posts) and ele["active"]:
            archived_posts_dicts = process_archived_posts(headers, model_id,username)
    if 'Messages' in args.posts or 'All' in args.posts:
            messages_dicts = process_messages(headers, model_id,username)
    if "Purchased" in args.posts or "All" in args.posts:
            purchased_dict=process_paid_post(headers, model_id,username)
    if ('Highlights'  in args.posts or 'Stories'  in args.posts or 'All' in args.posts)   and ele["active"]:
            highlights_tuple = process_highlights(headers, model_id,username)  
            if 'Highlights'  in args.posts:
                highlights_dicts=highlights_tuple[0]
            if 'Stories'  in args.posts:
                stories_dicts=highlights_tuple[1]   
            if 'All' in args.posts:
                highlights_dicts=highlights_tuple[0]
                stories_dicts=highlights_tuple[1]               
    return posts_filter(list(chain(*[profile_dicts  , timeline_posts_dicts ,pinned_post_dict,purchased_dict,
            archived_posts_dicts , highlights_dicts , messages_dicts,stories_dicts]))

)

def posts_filter(posts):
    filtersettings=config.read_config()["config"].get('filter')
    output=[]
    ids=set()
    for post in posts:
        if not post.id or post.id not in ids:
            output.append(post)
            ids.add(post.id)
    if isinstance(filtersettings,str):
        filtersettings=filtersettings.split(",")
    if isinstance(filtersettings,list):
        filtersettings=list(map(lambda x:x.lower().replace(" ",""),filtersettings))
        filtersettings=list(filter(lambda x:x!="",filtersettings))
        if len(filtersettings)==0:
            return posts
        console.print(f"filtering post to {filtersettings}")
        return list(filter(lambda x:x.mediatype.lower() in filtersettings,output))
    else:
        console.print("The settings you picked for the filter are not valid\nNot Filtering")
        return output
        


def do_database_migration():
    operations.user_db_migration()


def get_usernames(parsed_subscriptions: list) -> list:
    usernames = [sub[0] for sub in parsed_subscriptions]
    return usernames


def get_model(parsed_subscriptions: list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding 
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions)

  
def get_model_inputsplit(commaString):
    def hyphenRange(hyphenString):
        x = [int(x) for x in hyphenString.split('-')]
        return range(x[0], x[-1]+1)
    return chain(*[hyphenRange(r) for r in list(filter(lambda x:x.isdigit(),re.split(',| ',commaString)))])

@Halo(text='Getting your subscriptions (this may take awhile)...')
def get_models(headers, subscribe_count) -> list:
    """
    Get user's subscriptions in form of a list.
    """
    list_subscriptions = asyncio.run(
        subscriptions.get_subscriptions(headers, subscribe_count))
    parsed_subscriptions = subscriptions.parse_subscriptions(
        list_subscriptions)
    return parsed_subscriptions

#check if auth is valid
def process_me(headers):
    my_profile = me.scrape_user(headers)
    name, username = me.parse_user(my_profile)
    subscribe_count=me.parse_subscriber_count(headers)
    me.print_user(name, username)
    return subscribe_count

def setfilter():
    if prompts.decide_filters_prompts()=="Yes":
        global args
        args=prompts.modify_filters_prompt(args)
        args_.changeargs(args)

def process_prompts():
    changeusernames=True
    while  True:
        args.posts=None
        result_main_prompt = prompts.main_prompt()
        if changeusernames and result_main_prompt in [0,1,2]:
            setfilter()
            getselected_usernames()
        #download
        if result_main_prompt == 0:
            check_auth()
            process_post()     

        # like a user's posts
        elif result_main_prompt == 1:
            check_auth()
            process_like()
        # Unlike a user's posts
        elif result_main_prompt == 2:
            check_auth()
            process_unlike()

        # elif result_main_prompt == 3:
        #     # Migrate from old database
        #     do_database_migration()
        

        elif result_main_prompt == 3:
            # Edit `auth.json` file
            auth.edit_auth()
        
        elif result_main_prompt == 4:
            # Edit `config.json` file
            config.edit_config()

        
    
        elif result_main_prompt == 5:
            # Display  `Profiles` menu
            result_profiles_prompt = prompts.profiles_prompt()

            if result_profiles_prompt == 0:
                # Change profiles
                profiles.change_profile()

            elif result_profiles_prompt == 1:
                # Edit a profile
                profiles_ = profiles.get_profiles()

                old_profile_name = prompts.edit_profiles_prompt(profiles_)
                new_profile_name = prompts.new_name_edit_profiles_prompt(
                    old_profile_name)

                profiles.edit_profile_name(old_profile_name, new_profile_name)

            elif result_profiles_prompt == 2:
                # Create a new profile
                profile_path = profiles.get_profile_path()
                profile_name = prompts.create_profiles_prompt()

                profiles.create_profile(profile_path, profile_name)

            elif result_profiles_prompt == 3:
                # Delete a profile
                profiles.delete_profile()

            elif result_profiles_prompt == 4:
                # View profiles
                profiles.print_profiles()
        console.print("Done With Run")
        if prompts.continue_prompt()=="No":
            break
        global selectedusers
        if selectedusers:
            changeusernames=False
            console.print(f"Currently Selected Users\n{list(map(lambda x:x['name'],selectedusers))}")
            if prompts.reset_username_prompt()=="Yes":
                selectedusers=None
                changeusernames=True
        


def process_post():
    profiles.print_current_profile()
    headers = auth.make_headers(auth.read_auth())
    init.print_sign_status(headers)
    userdata=getselected_usernames()
    for ele in userdata:
        print(f"Getting Selected post type(s) for {ele['name']}\nSubscription Active: {ele['active']}")
        try:
            model_id = profile.get_id(headers, ele["name"])
            create_tables(model_id,ele['name'])
            operations.write_profile_table(model_id,ele['name'])
            combined_urls=process_areas(headers, ele, model_id)
            asyncio.run(download.process_dicts(
            ele["name"],
            model_id,
            combined_urls,
            forced=args.dupe,
            ))
        except Exception as e:
            console.print("run failed with exception: ", e)
    
    

def process_like():
    profiles.print_current_profile()
    headers = auth.make_headers(auth.read_auth())
    userdata=getselected_usernames()
    for ele in list(filter(lambda x: x["active"],userdata)):
            model_id = profile.get_id(headers, ele["name"])
            posts = like.get_posts(headers, model_id,ele["name"])
            unfavorited_posts = like.filter_for_unfavorited(posts)
            post_ids = like.get_post_ids(unfavorited_posts)
            like.like(headers, model_id, ele["name"], post_ids)

def process_unlike():
    profiles.print_current_profile()
    headers = auth.make_headers(auth.read_auth())
    init.print_sign_status(headers)
    userdata=getselected_usernames()
    for ele in list(filter(lambda x: x["active"],userdata)):
            model_id = profile.get_id(headers, ele["name"])
            posts = like.get_posts(headers, model_id,ele['name'])
            favorited_posts = like.filter_for_favorited(posts)
            post_ids = like.get_post_ids(favorited_posts)
            like.unlike(headers, model_id, ele["name"], post_ids)

@contextmanager
def asuppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr=sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:  
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def set_schedule(*params):
    [schedule.every(args.daemon).minutes.do(jobqueue.put,param) for param in params]
    while True:
        schedule.run_pending()
        time.sleep(30)


## run script once or on schedule based on args
def run(*params):
    # get usernames prior to potentially supressing output
    check_auth()
    getselected_usernames()
    console.print(f"starting script daemon: {args.daemon!=None} silent-mode: {args.silent}")    
    if args.silent:
        with suppress_stdout():
            run_helper(*params)
    else:
        run_helper(*params)
    console.print("script finished")

def run_helper(*params):
    [param() for param in params]    
    if args.daemon:
        global jobqueue
        jobqueue=queue.Queue()
        worker_thread = threading.Thread(target=set_schedule,args=[*params])
        worker_thread.start()
        while True:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
                
def check_auth():
    status=None
    while status!="UP":
        headers = auth.make_headers(auth.read_auth())
        status=init.getstatus(headers)
        if status=="DOWN":
            auth.make_auth(auth=auth.read_auth())
            continue
        break
        

    

       

def getselected_usernames():
    #username list will be retrived once per run
    global selectedusers
    if selectedusers:
        return selectedusers

    
    headers = auth.make_headers(auth.read_auth())
    subscribe_count = process_me(headers)
    parsed_subscriptions = get_models(headers, subscribe_count)
    filter_subscriptions=filteruserHelper(parsed_subscriptions )
    if args.username and "ALL" in args.username:
        selectedusers=filter_subscriptions
    

    elif args.username:
        userSelect=set(args.username)
        selectedusers=list(filter(lambda x:x["name"] in userSelect,filter_subscriptions))
    #manually select usernames
    else:
        selectedusers= get_model(filter_subscriptions)
    #remove dupes
    return selectedusers
def filteruserHelper(usernames):
    #paid/free
    filterusername=usernames
    if args.account_type=="paid":
        filterusername=list(filter(lambda x:x["data"]["subscribePrice"]>0,filterusername))
    if args.account_type=="free":
        filterusername=list(filter(lambda x:x["data"]["subscribePrice"]==0,filterusername))
    if args.renewal=="acive":
        filterusername=list(filter(lambda x:x["data"]["subscribedOn"]==True,filterusername))     
    if args.renewal=="disabled":
        filterusername=list(filter(lambda x:x["data"]["subscribedOn"]==False,filterusername))      
    if args.sub_status=="active":
        filterusername=list(filter(lambda x:x["data"]["subscribedIsExpiredNow"]==False,filterusername))     
    if args.sub_status=="expired":
        filterusername=list(filter(lambda x:x["data"]["subscribedIsExpiredNow"]==True,filterusername))      
    return filterusername


def create_tables(model_id,username):
    operations.create_post_table(model_id,username)
    operations.create_message_table(model_id,username)
    operations.create_media_table(model_id,username)
    operations.create_products_table(model_id,username)
    operations.create_others_table(model_id,username)
    operations.create_profile_table(model_id,username)
    operations.create_stories_table(model_id,username)

@contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr=sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:  
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

args=args_.getargs()
def main():
    with exit.DelayedKeyboardInterrupt(paths.cleanup,False):
        try:
            scrapper()
        except Exception as E:
            None
            # console.print(E)
            # console.print(traceback.format_exc(), style="white")
        quit()
def scrapper():
    if platform.system == 'Windows':
        os.system('color')
    # try:
    #     webbrowser.open(donateEP)
    # except:
    #     pass
    global selectedusers
    selectedusers=None


    
    if len(list(filter(lambda x:x!=None and x!=False,[args.action,args.posts])))==0:
        if args.daemon:
            console.print("You need to pass at least one scraping method\n--action\n--posts\n--purchase\nAre all valid options. Skipping and going to menu")
        process_prompts()
        sys.exit(0)
    



    if args.posts: 
        check_auth()
        run(process_post)        
    if args.action=="like":
        check_auth()
        run(process_like)
    if args.action=="unlike":
        check_auth()    
        run(process_unlike)  

if __name__ == '__main__':
    main()


