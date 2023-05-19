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
import traceback
import schedule
import threading
import queue
import logging
import textwrap
from contextlib import contextmanager
import timeit
from itertools import chain
import re
from rich.console import Console
import webbrowser
from halo import Halo
import arrow
import ofscraper.prompts.prompts as prompts
import ofscraper.api.messages as messages
import ofscraper.db.operations as operations
import ofscraper.api.posts as posts_
import ofscraper.utils.args as args_
import ofscraper.utils.paths as paths
import ofscraper.utils.exit as exit
import ofscraper.api.paid as paid
import ofscraper.api.highlights as highlights
import ofscraper.api.timeline as timeline
import ofscraper.api.profile as profile
import ofscraper.utils.config as config
import ofscraper.api.subscriptions as subscriptions
import ofscraper.api.me as me
import ofscraper.utils.auth as auth
import ofscraper.utils.profiles as profiles
import ofscraper.api.init as init
import ofscraper.utils.download as download
import ofscraper.interaction.like as like
import ofscraper.utils.logger as logger
import ofscraper.utils.args as args_
import ofscraper.constants as constants



console=Console()
log=logger.init_logger(logging.getLogger(__package__))
args=args_.getargs()
log.debug(args)
f = open(os.devnull, 'w')

@Halo(stream=sys.stdout if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f ,text='Getting messages...')
def process_messages(headers, model_id,username):
    messages_ =asyncio.run(messages.get_messages(headers,  model_id)) 
    messages_=list(map(lambda x:posts_.Post(x,model_id,username),messages_))
    log.debug(f"[bold]Messages Media Count with locked[/bold] {sum(map(lambda x:len(x.allmedia),messages_))}")
    log.debug("Removing locked messages media")
    for message in messages_:
     operations.write_messages_table(message)
    output=[]
    [ output.extend(message.media) for message in messages_]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

@Halo(stream=sys.stdout if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f,text='Getting Paid Content...')
def process_paid_post(model_id,username):
    paid_content=paid.scrape_paid(username)
    paid_content=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="paid"),paid_content))
    log.debug(f"[bold]Paid Media Count with locked[/bold] {sum(map(lambda x:len(x.allmedia),paid_content))}")
    log.debug("Removing locked paid media")
    for post in paid_content:
        operations.write_post_table(post,model_id,username)
    output=[]
    [output.extend(post.media) for post in paid_content]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

         

@Halo(stream=sys.stdout  if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f,text='Getting highlights and stories...\n')
def process_highlights(headers, model_id,username):
    highlights_, stories = highlights.scrape_highlights(headers, model_id)
    highlights_, stories=list(map(lambda x:posts_.Post(x,model_id,username,responsetype="highlights"),highlights_)),\
    list(map(lambda x:posts_.Post(x,model_id,username,responsetype="stories"),stories))
    log.debug(f"[bold]Combined Story and Highlight Media count[/bold] {sum(map(lambda x:len(x.allmedia), highlights_))+sum(map(lambda x:len(x.allmedia), stories))}")
    for post in highlights_:
        operations.write_stories_table(post,model_id,username)
    for post in stories:
        operations.write_stories_table(post,model_id,username)   
    output=[]
    output2=[]
    [ output.extend(highlight.media) for highlight in highlights_]
    [ output2.extend(stories.media) for stories in stories]
    return list(filter(lambda x:isinstance(x,posts_.Media),output)),list(filter(lambda x:isinstance(x,posts_.Media),output2))

     






@Halo(stream=sys.stdout if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f,text='Getting timeline media...')
def process_timeline_posts(headers, model_id,username):
    timeline_posts = asyncio.run(timeline.get_timeline_post(headers, model_id))
    timeline_posts  =list(map(lambda x:posts_.Post(x,model_id,username,"timeline"), timeline_posts ))
    log.debug(f"[bold]Timeline Media Count with locked[/bold] {sum(map(lambda x:len(x.allmedia),timeline_posts))}")
    log.debug("Removing locked timeline media")
    for post in timeline_posts:
        operations.write_post_table(post,model_id,username)
    output=[]
    [output.extend(post.media) for post in  timeline_posts ]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))

@Halo(stream=sys.stdout if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f,text='Getting archived media...')
def process_archived_posts(headers, model_id,username):
    archived_posts = timeline.get_archive_post(headers, model_id)
    archived_posts =list(map(lambda x:posts_.Post(x,model_id,username),archived_posts ))
    log.debug(f"[bold]Archived Media Count with locked[/bold] {sum(map(lambda x:len(x.allmedia),archived_posts))}")
    log.debug("Removing locked archived media")

    for post in archived_posts:
        operations.write_post_table(post,model_id,username)
    output=[]
    [ output.extend(post.media) for post in archived_posts ]
    return list(filter(lambda x:isinstance(x,posts_.Media),output))




@Halo(stream=sys.stdout if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f,text='Getting pinned media...')
def process_pinned_posts(headers, model_id,username):
    pinned_posts = timeline.get_pinned_post(headers, model_id,username)
    pinned_posts =list(map(lambda x:posts_.Post(x,model_id,username,"pinned"),pinned_posts ))
    log.debug(f"[bold]Pinned Media Count with locked[/bold] {sum(map(lambda x:len(x.allmedia),pinned_posts))}")
    log.debug("Removing locked pinned media")
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
    avatars=list(filter(lambda x:x.filename=='avatar',output))
    if len(avatars)>0:
        log.info(f"Avatar : {avatars[0].url}")
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
            purchased_dict=process_paid_post(model_id,username)
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

def posts_filter(media):
    filtersettings=config.get_filter(config.read_config())
    output=[]
    ids=set()
    log.info("Removing duplicate media")
    log.debug(f"[bold]Combined Media Count with dupes[/bold]  {len(media)}")
    for item in media:
        if not item.id or item.id not in ids:
            output.append(item)
            ids.add(item.id)
    log.debug(f"[bold]Combined Media Count without dupes[/bold] {len(output)}")
    output=list(sorted(output,key=lambda x:x.date,reverse=True))
    if isinstance(filtersettings,str):
        filtersettings=filtersettings.split(",")
    if isinstance(filtersettings,list):
        filtersettings=list(map(lambda x:x.lower().replace(" ",""),filtersettings))
        filtersettings=list(filter(lambda x:x!="",filtersettings))
        if len(filtersettings)==0:
            return media
        log.info(f"filtering Media to {','.join(filtersettings)}")
        output= list(filter(lambda x:x.mediatype.lower() in filtersettings,output))
    else:
        log.info("The settings you picked for the filter are not valid\nNot Filtering")
        log.debug(f"[bold]Combined Media Count Filtered:[/bold] {len(output)}")
    return output

        



def get_usernames(parsed_subscriptions: list) -> list:
    usernames = [sub[0] for sub in parsed_subscriptions]
    log.debug(f"[bold]Usernames on account:[/bold] {usernames}")
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

@Halo(stream=sys.stdout if logging.getLogger("ofscraper").handlers[1].level<constants.SUPPRESS_LOG_LEVEL else f,text='Getting your subscriptions (this may take awhile)...') 
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
    
    while  True:
        args.posts=[]
        result_main_prompt = prompts.main_prompt()
     
        #download
        if result_main_prompt == 0:
            check_auth()
            check_config()
            process_post()     

        # like a user's posts
        elif result_main_prompt == 1:
            check_auth()
            process_like()
        # Unlike a user's posts
        elif result_main_prompt == 2:
            check_auth()
            process_unlike()
        
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
        if prompts.continue_prompt()=="No":
            break
  
        


def process_post():
    with scrape_context_manager():
        profiles.print_current_profile()
        headers = auth.make_headers(auth.read_auth())
        init.print_sign_status(headers)
        userdata=getselected_usernames()
        for ele in userdata:
            if args.posts:
                log.info(f"Getting {','.join(args.posts)} for [bold]{ele['name']}[/bold]\n[bold]Subscription Active:[/bold] {ele['active']}")
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
                log.traceback(f"failed with exception: {e}")
                log.traceback(traceback.format_exc())
        
        

def process_like():
    with scrape_context_manager():
        profiles.print_current_profile()
        headers = auth.make_headers(auth.read_auth())
        userdata=getselected_usernames()
        for ele in list(filter(lambda x: x["active"],userdata)):
                model_id = profile.get_id(headers, ele["name"])
                posts = like.get_posts(headers, model_id)
                unfavorited_posts = like.filter_for_unfavorited(posts)
                post_ids = like.get_post_ids(unfavorited_posts)
                like.like(headers, model_id, ele["name"], post_ids)

def process_unlike():
    with scrape_context_manager(): 
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
#Adds a function to the job queue
def set_schedule(*functs):
    [schedule.every(args.daemon).minutes.do(jobqueue.put,funct) for funct in functs]
    while True:
        schedule.run_pending()
        time.sleep(30)



## run script once or on schedule based on args
def run(*functs):
    # get usernames prior to potentially supressing output
    check_auth()
    getselected_usernames()
   
    if args.output=="PROMPT":
        log.info(f"[bold]silent-mode on[/bold]")    
    if args.daemon:
        log.info(f"[bold]daemon mode on[/bold]")   
    run_helper(*functs)


def run_helper(*functs):
    # run each function once
    [funct() for funct in functs]    
    if args.daemon:
        global jobqueue
        jobqueue=queue.Queue()
        worker_thread = threading.Thread(target=set_schedule,args=[*functs])
        worker_thread.start()
        # Check if jobqueue has function
        while True:
            job_func = jobqueue.get()
            job_func()
            jobqueue.task_done()
            log.debug(schedule.jobs)
                
def check_auth():
    status=None
    while status!="UP":
        headers = auth.make_headers(auth.read_auth())
        status=init.getstatus(headers)
        if status=="DOWN":
            log.error("Auth Failed")
            auth.make_auth(auth=auth.read_auth())
            continue
        break
        

def check_config():
    while not  paths.mp4decryptchecker(config.get_mp4decrypt(config.read_config())):
        console.print("You need to select path for mp4decrypt\n\n")
        log.debug(f"[bold]current mp4decrypt path[/bold] {config.get_mp4decrypt(config.read_config())}")
        config.update_mp4decrypt()
    while not  paths.ffmpegchecker(config.get_ffmpeg(config.read_config())):
        console.print("You need to select path for ffmpeg\n\n")
        log.debug(f"[bold]current ffmpeg path[/bold] {config.get_ffmpeg(config.read_config())}")
        config.update_ffmpeg()
    log.debug(f"[bold]final mp4decrypt path[/bold] {config.get_mp4decrypt(config.read_config())}")
    log.debug(f"[bold]final ffmpeg path[/bold] {config.get_ffmpeg(config.read_config())}")



       

def getselected_usernames():
    #username list will be retrived once per run
    global selectedusers
    if selectedusers:
        if len(args.posts)>0:
            return selectedusers
        elif prompts.reset_username_prompt()=="No":
           return selectedusers
        else:
            setfilter()
    else:
        if len(args.posts)==0:
            setfilter()
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
def scrape_context_manager():
        
        # Before yield as the enter method

        start = timeit.default_timer()
        log.error(
f"""
==============================                            
[bold]starting script[/bold]
==============================
"""
    

    )
        yield
        end=timeit.default_timer()
        log.error(f"""
===========================
[bold]Script Finished[/bold]
Run Time:  [bold]{str(arrow.get(end)-arrow.get(start)).split(".")[0]}[/bold]
===========================
""")
        None   
def main():
    
# Python program for creating a
# context manager using @contextmanager
# decorator
 
    with exit.DelayedKeyboardInterrupt(paths.cleanup,False):
        try:
 
            scrapper()

            

        except Exception as E:
            log.traceback(E)
            log.traceback(traceback.format_exc())
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
    functs=[]
    if len(args.posts)==0 and not args.action:
        if args.daemon:
                    log.warning("You need to pass at least one scraping method\n--action\n--posts\n--purchase\nAre all valid options. Skipping and going to menu")
        process_prompts()
        return
    check_auth()
    check_config()
    if len(args.posts)>0: 
        functs.append(process_post)      
    elif args.action=="like":
        functs.append(process_like)
    elif args.action=="unlike":
        functs.append(process_unlike)
    run(*functs)  
  
       



