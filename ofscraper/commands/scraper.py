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
import os
import sys
import platform
import time
import traceback
import schedule
import threading
import queue
import logging
from contextlib import contextmanager
import timeit
import arrow
import ofscraper.prompts.prompts as prompts
import ofscraper.db.operations as operations
import ofscraper.utils.args as args_
import ofscraper.utils.paths as paths
import ofscraper.utils.exit as exit
import ofscraper.api.profile as profile
import ofscraper.utils.config as config
import ofscraper.utils.auth as auth
import ofscraper.utils.profiles as profiles
import ofscraper.api.init as init
import ofscraper.utils.download as download
import ofscraper.interaction.like as like
import ofscraper.utils.args as args_
import ofscraper.utils.filters as filters
import ofscraper.utils.stdout as stdout
import ofscraper.utils.userselector as userselector
import ofscraper.utils.console as console
import ofscraper.utils.of as OF
import ofscraper.utils.exit as exit
import ofscraper.utils.misc as misc

log=logging.getLogger("shared")

@exit.exit_wrapper
def process_prompts():
    
    while  True:
        args_.getargs().posts=[]
        result_main_prompt = prompts.main_prompt()
     
        #download
        if result_main_prompt == 0:
            check_auth()
            check_config()
            run(process_post)


        # like a user's posts
        elif result_main_prompt == 1:
            check_auth()  
            check_config()
            run(process_like)

        # Unlike a user's posts
        elif result_main_prompt == 2:
            check_auth()  
            check_config()
            run(process_unlike)

        
        elif result_main_prompt == 3:
            # Edit `auth.json` file
            auth.edit_auth()
        
        elif result_main_prompt == 4:
            # Edit `config.json` file
            config.edit_config()

        elif result_main_prompt == 5:
            # Edit `config.json` file
            config.edit_config_advanced()

        
    
        elif result_main_prompt == 6:
            # Display  `Profiles` menu
            result_profiles_prompt = prompts.profiles_prompt()

            if result_profiles_prompt == 0:
                # Change profiles
                profiles.change_profile()

            elif result_profiles_prompt == 1:
                # Edit a profile
                profiles.edit_profile_name()

            elif result_profiles_prompt == 2:
                # Create a new profile

                profiles.create_profile()

            elif result_profiles_prompt == 3:
                # Delete a profile
                profiles.delete_profile()

            elif result_profiles_prompt == 4:
                # View profiles
                profiles.print_profiles()
        if prompts.continue_prompt()=="No":
            break
  
        







@exit.exit_wrapper
def process_post():
    if args_.getargs().users_first:
         process_post_user_first()
    else:
        normal_post_process()

@exit.exit_wrapper           
def process_post_user_first():
     with scrape_context_manager():
        profiles.print_current_profile()
        init.print_sign_status()
        if args_.getargs().users_first:
            output=[]
            userdata=userselector.getselected_usernames(rescan=False)
            length=len(userdata)
            for count,ele in enumerate(userdata):
                log.info(f"Progress {count+1}/{length} model")
                if args_.getargs().posts:
                    log.info(f"Getting {','.join(args_.getargs().posts)} for [bold]{ele['name']}[/bold]\n[bold]Subscription Active:[/bold] {ele['active']}")
                try:
                    model_id = profile.get_id( ele["name"])
                    operations.write_profile_table(model_id=model_id,username=ele['name'])
                    output.extend(OF.process_areas( ele, model_id)) 
                except Exception as e:
                    log.traceback(f"failed with exception: {e}")
                    log.traceback(traceback.format_exc())               
            if args_.getargs().scrape_paid:
                output.extend(OF.process_all_paid())
            user_dict={}
            [user_dict.update({ele.post.model_id:user_dict.get(ele.post.model_id,[])+[ele]}) for ele in output]
            for value in user_dict.values():
                model_id =value[0].post.model_id
                username=value[0].post.username
                
                operations.create_tables(model_id=model_id,username=username)
                operations.create_backup(model_id,username)
                operations.write_profile_table(model_id=model_id,username=username)
                results=misc.download_picker(
                    username,
                    model_id,
                    value,
                    )
                

@exit.exit_wrapper
def normal_post_process():
    with scrape_context_manager():
        profiles.print_current_profile()
        init.print_sign_status()
        userdata=userselector.getselected_usernames(rescan=False)
        length=len(userdata)
        for count,ele in enumerate(userdata):
            log.error(f"Progress {count+1}/{length} model")
            if args_.getargs().posts:
                log.error(f"Getting {','.join(args_.getargs().posts)} for [bold]{ele['name']}[/bold]\n[bold]Subscription Active:[/bold] {ele['active']}")
            try:
                model_id = profile.get_id( ele["name"])
                operations.create_tables(model_id,ele['name'])
                operations.create_backup(model_id,ele['name'])
                operations.write_profile_table(model_id=model_id,username=ele['name'])
                combined_urls=OF.process_areas( ele, model_id)
                misc.download_picker(
                    ele["name"],
                    model_id,
                    combined_urls
                    )
            except Exception as e:
                log.traceback(f"failed with exception: {e}")
                log.traceback(traceback.format_exc())
        
        if args_.getargs().scrape_paid:
            try:
                user_dict={}
                [user_dict.update({ele.post.model_id:user_dict.get(ele.post.model_id,[])+[ele]}) for ele in OF.process_all_paid()]
                for value in user_dict.values():
                    try:
                        model_id =value[0].post.model_id
                        username=value[0].post.username
                        log.info(f"inserting {len(value)} items into  into media table for {username}")
                        asyncio.run(operations.batch_mediainsert( value,operations.write_media_table,model_id=model_id,username=username,downloaded=False))  
                        operations.create_tables(model_id=model_id,username=username)
                        operations.create_backup(model_id,username)                    
                        operations.write_profile_table(model_id=model_id,username=username)
                        misc.download_picker(
                            username,
                            model_id,
                            value,
                            )
                    except Exception as E:
                        log.traceback(f"failed with exception: {E}")
                        log.traceback(traceback.format_exc())
            except Exception as e:
                log.traceback(f"failed with exception: {e}")
                log.traceback(traceback.format_exc())     

@exit.exit_wrapper
def process_like():
    with scrape_context_manager():
        profiles.print_current_profile()
        init.print_sign_status()
        userdata=userselector.getselected_usernames(rescan=False)
        active=list(filter(lambda x: x["active"],userdata))
        length=len(active)
        with stdout.lowstdout():
            for count,ele in enumerate(active):
                    log.info(f"Progress {count+1}/{length} model")
                    model_id = profile.get_id( ele["name"])
                    posts = like.get_posts(model_id, ele["name"])
                    unfavorited_posts = like.filter_for_unfavorited(posts)  
                    unfavorited_posts=filters.timeline_array_filter(unfavorited_posts)   
                    log.debug(f"[bold]Number of unliked posts left after date filters[/bold] {len(unfavorited_posts)}")
                    post_ids = like.get_post_ids(unfavorited_posts)
                    log.debug(f"[bold]Final Number of open and likable post[/bold] {len(post_ids)}")
                    like.like( model_id, ele["name"], post_ids)

@exit.exit_wrapper
def process_unlike():
    with scrape_context_manager(): 
        profiles.print_current_profile()
        init.print_sign_status()
        userdata=userselector.getselected_usernames(rescan=False)
        active=list(filter(lambda x: x["active"],userdata))
        length=len(active)
        with stdout.lowstdout():
            for count,ele in enumerate(active):
                    log.info(f"Progress {count+1}/{length} model")
                    model_id = profile.get_id( ele["name"])
                    posts = like.get_posts( model_id)
                    favorited_posts = like.filter_for_favorited(posts)
                    favorited_posts=filters.timeline_array_filter(favorited_posts) 
                    log.debug(f"[bold]Number of liked posts left after date filters[/bold] {len(favorited_posts)}")
                    post_ids = like.get_post_ids(favorited_posts)
                    log.debug(f"[bold]Final Number of open and unlikable post[/bold] {len(post_ids)}")
                    like.unlike( model_id, ele["name"], post_ids)
#Adds a function to the job queue
def set_schedule(*functs):
    [schedule.every(args_.getargs().daemon).minutes.do(jobqueue.put,funct) for funct in functs]
    while len(schedule.jobs)>0:
        schedule.run_pending()
        time.sleep(30)



## run script once or on schedule based on args
def run(*functs):
    # get usernames prior to potentially supressing output
    check_auth()
    if args_.getargs().output=="PROMPT":
        log.info(f"[bold]silent-mode on[/bold]")    
    if args_.getargs().daemon:
        log.info(f"[bold]daemon mode on[/bold]")   
    run_helper(*functs)


def run_helper(*functs):
    # run each function once
    global jobqueue
    jobqueue=queue.Queue()
    [jobqueue.put(funct) for funct in functs]
    worker_thread=None
          
    try:
        if args_.getargs().daemon:
                worker_thread = threading.Thread(target=set_schedule,args=[*functs],daemon=True)
                worker_thread.start()
                # Check if jobqueue has function
                while True:
                    log.debug(schedule.jobs)
                    job_func = jobqueue.get()
                    job_func()
                    jobqueue.task_done()
                    userselector.getselected_usernames(rescan=True)
    except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    schedule.clear()
                raise KeyboardInterrupt
            except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    schedule.clear()
                    raise E
    except Exception as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    schedule.clear()
                raise E
            except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    schedule.clear()
                    raise E
            
            #update selected user
    else:
        try:
            userselector.getselected_usernames(rescan=True,reset=True)
            for _ in functs:
                job_func = jobqueue.get()
                job_func()
                jobqueue.task_done()
        except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    schedule.clear()
                    raise KeyboardInterrupt
        except Exception as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    raise E
            except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    raise E  
                
def check_auth():
    status=None
    while status!="UP":
        status=init.getstatus()
        if status=="DOWN":
            log.error("Auth Failed")
            auth.make_auth(auth=auth.read_auth())
            continue
        break
        

def check_config():
    while not  paths.mp4decryptchecker(config.get_mp4decrypt(config.read_config())):
        console.get_shared_console().print("You need to select path for mp4decrypt\n\n")
        log.debug(f"[bold]current mp4decrypt path[/bold] {config.get_mp4decrypt(config.read_config())}")
        config.update_mp4decrypt()
    while not  paths.ffmpegchecker(config.get_ffmpeg(config.read_config())):
        console.get_shared_console().print("You need to select path for ffmpeg\n\n")
        log.debug(f"[bold]current ffmpeg path[/bold] {config.get_ffmpeg(config.read_config())}")
        config.update_ffmpeg()
    log.debug(f"[bold]final mp4decrypt path[/bold] {config.get_mp4decrypt(config.read_config())}")
    log.debug(f"[bold]final ffmpeg path[/bold] {config.get_ffmpeg(config.read_config())}")




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
def print_start():
    with stdout.lowstdout():
        console.get_shared_console().print(
            f"[bold green]Welcome to OF-Scraper Version {args_.getargs().version}[/bold green]"
        )                
def main():
 
        try:    
            print_start()
            paths.cleanup()
            paths.cleanDB()
            misc.check_cdm()
            scrapper()
            paths.cleanup()
            paths.cleanDB()
        except KeyboardInterrupt as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    paths.cleanup()
                    paths.cleanDB()
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                    raise KeyboardInterrupt
        except Exception as E:
            try:
                with exit.DelayedKeyboardInterrupt():
                    paths.cleanup()
                    paths.cleanDB()
                    log.traceback(E)
                    log.traceback(traceback.format_exc())
                    raise E
            except KeyboardInterrupt:
                with exit.DelayedKeyboardInterrupt():
                    raise E
def scrapper():
    if platform.system() == 'Windows':
        os.system('color')
    global selectedusers
    selectedusers=None
    functs=[]
    if len(args_.getargs().posts)==0 and not args_.getargs().action and not args_.getargs().scrape_paid:
        if args_.getargs().daemon:
                    log.error("You need to pass at least one scraping method\n--action\n--posts\n--purchase\nAre all valid options. Skipping and going to menu")
        process_prompts()
        return
    check_auth()
    check_config()
    if len(args_.getargs().posts)>0 or args_.getargs().scrape_paid: 
        functs.append(process_post)      
    elif args_.getargs().action=="like":
        functs.append(process_like)
    elif args_.getargs().action=="unlike":
        functs.append(process_unlike)
    run(*functs)  
  
       



