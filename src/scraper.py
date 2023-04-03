r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import argparse
import asyncio
import datetime
import os
import sys
import platform
from random import randint, choice
from time import sleep
import time
from datetime import datetime, timedelta
import schedule
from contextlib import contextmanager
import threading
import queue
import functools
from itertools import chain
import re
from rich.console import Console
console=Console()
from .constants import donateEP
from .api import init, highlights, me, messages, posts, profile, subscriptions, paid
from .db import operations
from .interaction import like
from .utils import auth, config, download, profiles, prompts
import webbrowser
from revolution import Revolution
from .utils.nap import nap_or_sleep
from .__version__ import  __version__






# @need_revolution("Getting messages...")
@Revolution(desc='Getting messages...')
def process_messages(headers, model_id):
    messages_ = messages.scrape_messages(headers, model_id)
    output=[]
    if messages_:
        [output.extend(messages.parse_messages([ele],model_id)) for ele in messages_]       
    return output

# @need_revolution("Getting highlights...")
@Revolution(desc='Getting highlights and stories...')
def process_highlights(headers, model_id):
    highlights_, stories = highlights.scrape_highlights(headers, model_id)
    highlight_list=highlights.parse_highlights(highlights_)
    stories_list=highlights.parse_stories(stories)
    return highlight_list,stories_list




# @need_revolution("Getting subscriptions...")
@Revolution(desc='Getting archived media...')
def process_archived_posts(headers, model_id):
    archived_posts = posts.scrape_archived_posts(headers, model_id)
    if archived_posts:
        archived_posts_urls = posts.parse_posts(archived_posts)
        return archived_posts_urls
    return []

# @need_revolution("Getting timeline media...")
@Revolution(desc='Getting timeline media...')
def process_timeline_posts(headers, model_id):
    timeline_posts = posts.scrape_timeline_posts(headers, model_id)
    if timeline_posts:
        timeline_posts_urls = posts.parse_posts(timeline_posts)
        return timeline_posts_urls
    return []


# @need_revolution("Getting pinned media...")
@Revolution(desc='Getting pinned media...')
def process_pinned_posts(headers, model_id):
    pinned_posts = posts.scrape_pinned_posts(headers, model_id)
    if pinned_posts:
        pinned_posts_urls = posts.parse_posts(pinned_posts)
        return pinned_posts_urls
    return []


def process_profile(headers, username) -> list:
    user_profile = profile.scrape_profile(headers, username)
    urls, info = profile.parse_profile(user_profile)
    profile.print_profile_info(info)
    return urls




def process_areas(headers, ele, model_id,selected=None) -> list:
    result_areas_prompt = list(map(lambda x:x.capitalize(),(selected or prompts.areas_prompt())
))
    pinned_posts_dicts = []
    timeline_posts_dicts  = []
    archived_posts_dicts  = []
    highlights_dicts  = []
    messages_dicts  = []
    stories_dicts=[]

    # profile_dicts  = process_profile(headers, ele["name"])
    profile_dicts=[]

    if ('Timeline' in result_areas_prompt or 'All' in result_areas_prompt) and ele["active"]:
            pinned_posts_dicts= process_pinned_posts(headers, model_id)
            timeline_posts_dicts = process_timeline_posts(headers, model_id)

    if ('Archived' in result_areas_prompt or 'All' in result_areas_prompt) and ele["active"]:
            archived_posts_dicts = process_archived_posts(headers, model_id)
    if 'Messages' in result_areas_prompt or 'All' in result_areas_prompt:
            messages_dicts = process_messages(headers, model_id)

    if ('Highlights'  in result_areas_prompt or 'Stories'  in result_areas_prompt or 'All' in result_areas_prompt)   and ele["active"]:
            highlights_tuple = process_highlights(headers, model_id)
            if 'All' in result_areas_prompt:
                highlights_dicts=highlights_tuple[0]
                stories_dicts=highlights_tuple[1]    
            elif 'Highlights'  in result_areas_prompt:
                highlights_dicts=highlights_tuple[0]
            elif 'Stories'  in result_areas_prompt:
                stories_dicts=highlights_tuple[1]    
    return list(chain(*[profile_dicts ,pinned_posts_dicts , timeline_posts_dicts ,
            archived_posts_dicts , highlights_dicts , messages_dicts,stories_dicts]))






def do_database_migration(path, model_id):
    results = operations.read_foreign_database(path)
    operations.write_from_foreign_database(results, model_id)


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


def get_models(headers, subscribe_count) -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with Revolution(desc='Getting your subscriptions (this may take awhile)...') as _:
        list_subscriptions = asyncio.run(
            subscriptions.get_subscriptions(headers, subscribe_count))
        parsed_subscriptions = subscriptions.parse_subscriptions(
            list_subscriptions)
    return parsed_subscriptions


def process_me(headers):
    my_profile = me.scrape_user(headers)
    name, username = me.parse_user(my_profile)
    subscribe_count=me.parse_subscriber_count(headers)
    me.print_user(name, username)
    return subscribe_count


def process_prompts():
    loop = process_prompts
    result_main_prompt = prompts.main_prompt()
    headers = auth.make_headers(auth.read_auth())
    if result_main_prompt in [0,1,2] and prompts.decide_filters_prompts()=="Yes":
        global args
        args=prompts.modify_filters_prompt(args)
    #download
    if result_main_prompt == 0:
        paid=prompts.download_paid_prompt()=="Yes"
        process_post()
        if paid:
            process_paid()

    # like a user's posts
    elif result_main_prompt == 2:
        process_like()
    # Unlike a user's posts
    elif result_main_prompt == 3:
        process_unlike()

    elif result_main_prompt == 4:
        # Migrate from old database
        path, username = prompts.database_prompt()
        model_id = profile.get_id(headers, username)
        do_database_migration(path, model_id)
     

    elif result_main_prompt == 5:
        # Edit `auth.json` file
        auth.edit_auth()
    
    elif result_main_prompt == 6:
        # Edit `config.json` file
        config.edit_config()

      
 
    elif result_main_prompt == 7:
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
        return
    global selectedusers
    if selectedusers and prompts.reset_username_prompt()=="Yes":
        getselected_usernames()
    loop()
def process_paid():


    profiles.print_current_profile()
    headers = auth.make_headers(auth.read_auth())

    init.print_sign_status(headers)
    userdata=getselected_usernames()
    for ele in userdata:
        print(f"Getting paid content for {ele['name']}")
        try:
            model_id = profile.get_id(headers, ele["name"])
            paid_content=paid.scrape_paid(ele["name"])
            paid_url=paid.parse_paid(paid_content)
            profile.print_paid_info(paid_url,ele["name"])
            asyncio.run(download.process_dicts_paid(
            headers,
            ele["name"],
            model_id,
            paid_url,
            forced=args.dupe,
            outpath=args.outpath
            ))
        except Exception as e:
            console.print("run failed with exception: ", e)


def process_post():
    profiles.print_current_profile()
    headers = auth.make_headers(auth.read_auth())
    init.print_sign_status(headers)
    userdata=getselected_usernames()
    for ele in userdata:
        print(f"Getting Selected post type(s) for {ele['name']}\nSubscription Active: {ele['active']}")
        try:
            model_id = profile.get_id(headers, ele["name"])
            combined_urls=process_areas(headers, ele, model_id,selected=args.posts)
            asyncio.run(download.process_dicts(
            headers,
            ele["name"],
            model_id,
            combined_urls,
            forced=args.dupe,
            outpath=args.outpath
            ))
        except Exception as e:
            console.print("run failed with exception: ", e)
    
    

def process_like():
    profiles.print_current_profile()
    headers = auth.make_headers(auth.read_auth())
    init.print_sign_status(headers)
    userdata=getselected_usernames()
    for ele in list(filter(lambda x: x["active"],userdata)):
            model_id = profile.get_id(headers, ele["name"])
            posts = like.get_posts(headers, model_id)
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
            posts = like.get_posts(headers, model_id)
            favorited_posts = like.filter_for_favorited(posts)
            post_ids = like.get_post_ids(favorited_posts)
            like.unlike(headers, model_id, ele["name"], post_ids)

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

def set_schedule(command,*params,**kwparams):
    schedule.every(args.daemon).minutes.do(jobqueue.put,functools.partial(command,*params,**kwparams))
    while True:
        schedule.run_pending()
        time.sleep(30)


## run script once or on schedule based on args
def run(command,*params,**kwparams):
    # get usernames prior to potentially supressing output
    getselected_usernames()
    console.print(f"starting script daemon:{args.daemon!=None} silent-mode:{args.silent}")    
    if args.silent:
        with suppress_stdout():
            run_helper(command,*params,**kwparams)
    else:
        run_helper(command,*params,**kwparams)
    console.print("script finished")

def run_helper(command,*params,**kwparams):   
    command(*params,**kwparams)
    if args.daemon:
        global jobqueue
        jobqueue=queue.Queue()
        worker_thread = threading.Thread(target=set_schedule,args=[command,*params],kwargs=kwparams)
        worker_thread.start()
        while True:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
                
def checkAuth():
    status=None
    while status!="UP":
        headers = auth.make_headers(auth.read_auth())
        status=init.print_sign_status(headers)
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
        selectedusers=list(filter(lambda x:x in userSelect,filter_subscriptions))
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



#force auth 
checkAuth()
def main():
    global args
    if platform.system == 'Windows':
        os.system('color')
    # try:
    #     webbrowser.open(donateEP)
    # except:
    #     pass


    parser = argparse.ArgumentParser()

    parser = argparse.ArgumentParser(add_help=False)   
    general=parser.add_argument_group("General",description="General Args")  
    general.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    general.add_argument('-h', '--help', action='help')

                                    
    general.add_argument(
        '-u', '--username', help="select which username to process (name,name2)\nSet to ALL for all users",type=lambda x: list(filter( lambda y:y!="",x.split(",")))
    )
    general.add_argument(
        '-d', '--daemon', help='run script in the background\nSet value to minimum minutes between script runs\nOverdue runs will run as soon as previous run finishes', type=int,default=None
    )
    general.add_argument(
        '-s', '--silent', help = 'mute output', action = 'store_true',default=False
    )
    post=parser.add_argument_group("Post",description="What type of post to scrape")                                      

    post.add_argument("-e","--dupe",action="store_true",default=False,help="Bypass the dupe check and redownload all files")
    post.add_argument(
        '-o', '--posts', help = 'Download content from a models wall',default=None,required=False,type = str.lower,choices=["highlights","all","archived","messages","timeline","stories"],nargs="+"
    )
    post.add_argument("-p","--purchased",action="store_true",default=False,help="Download individually purchased content")
    post.add_argument("-a","--action",default=None,help="perform like or unlike action on each post",choices=["like","unlike"])

     #Filters for accounts
    filters=parser.add_argument_group("filters",description="Filters out usernames based on selected parameters")
    
    filters.add_argument(
        '-t', '--account-type', help = 'Filter Free or paid accounts',default=None,required=False,type = str.lower,choices=["paid","free"]
    )
    filters.add_argument(
        '-r', '--renewal', help = 'Filter by whether renewal is on or off for account',default=None,required=False,type = str.lower,choices=["active","disabled"]
    )
    filters.add_argument(
        '-ss', '--sub-status', help = 'Filter by whether or not your subscription has expired or not',default=None,required=False,type = str.lower,choices=["active","expired"]
    )

     #Paths
    paths=parser.add_argument_group("paths",description="Change or forced paths in program")

    paths.add_argument(
        '-op', '--outpath', help = 'Force downloading media into this directory',default=None,required=False
    )
    args = parser.parse_args()
    global selectedusers
    selectedusers=None
    if len(list(filter(lambda x:x!=None and x!=False,[args.action,args.purchased,args.posts])))==0:
        process_prompts()
        sys.exit(0)
    
    #force off
    
   #process user selected option


    if args.posts: 
        run(process_post)        
    if args.purchased:
        run(process_paid)
    if args.action=="like":
        run(process_like)
    if args.action=="unlike":
        run(process_unlike)  


if __name__ == '__main__':
    main()
