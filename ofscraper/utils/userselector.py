import asyncio
import time
import logging
import arrow
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn
)
from rich.style import Style

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args as args_
import ofscraper.api.subscriptions as subscriptions
import ofscraper.api.me as me
import ofscraper.utils.auth as auth
import ofscraper.utils.args as args_
import ofscraper.utils.stdout as stdout




ALL_SUBS=None
PARSED_SUBS=None
log=logging.getLogger(__package__)
args=args_.getargs()

def getselected_usernames(rescan=False,reset=False):
    #username list will be retrived every time reset==True
    global ALL_SUBS
    global PARSED_SUBS
    if "Skip" in args.posts:
        return []
    if reset==True and PARSED_SUBS:
        if prompts.reset_username_prompt()=="Yes":
           PARSED_SUBS=None
           args.username=None
           args_.changeargs(args)
    if rescan==True:
        PARSED_SUBS=None
    if not PARSED_SUBS or not args.username:
        all_subs_helper()
        parsed_subscriptions_helper()
    return PARSED_SUBS


 
    
def all_subs_helper(): 
    headers = auth.make_headers(auth.read_auth())
    subscribe_count = process_me(headers)
    global ALL_SUBS
    ALL_SUBS= get_models( subscribe_count)


def parsed_subscriptions_helper(force=False):
    global ALL_SUBS
    global PARSED_SUBS
    if not args.username:
        selectedusers=get_model(ALL_SUBS)
        args.username=list(map(lambda x:x["name"],selectedusers))
        PARSED_SUBS=selectedusers
        args_.changeargs(args)  
    elif "ALL" in args.username:
        PARSED_SUBS=filterNSort(ALL_SUBS)
    elif args.username:
        usernameset=set(args.username)
        PARSED_SUBS=list(filter(lambda x:x["name"] in usernameset,ALL_SUBS))
    return PARSED_SUBS
        
       

def setfilter():
    if prompts.decide_filters_prompt()=="Yes":
        global args
        args=prompts.modify_filters_prompt(args)

 
def setsort():
    if prompts.decide_sort_prompt()=="Yes":
        global args
        args=prompts.modify_sort_prompt(args)

def filterNSort(usernames):


    #paid/free
    filterusername=usernames
    log.debug(f"username count no filters: {len(filterusername)}")
    dateNow=arrow.now()
    if args.account_type=="paid":
        filterusername=list(filter(lambda x:(x.get("price") or 0)>0,filterusername))
        log.debug(f"+paid filter username count: {len(filterusername)}")

    elif args.account_type=="free":
        filterusername=list(filter(lambda x:(x.get("price") or 0)==0,filterusername))    
        log.debug(f"+free filter username count: {len(filterusername)}")
    
    if args.renewal=="active":
        filterusername=list(filter(lambda x:x.get("renewed")!=None,filterusername))
        log.debug(f"+active renewal filter username count: {len(filterusername)}")

    elif args.renewal=="disabled":
        filterusername=list(filter(lambda x:x.get("renewed")==None,filterusername))  
        log.debug(f"+disabled renewal filter username count: {len(filterusername)}")

    if args.sub_status=="active":
        filterusername=list(filter(lambda x:x.get("subscribed")!=None,filterusername)) 
        log.debug(f"+active subscribtion filter username count: {len(filterusername)}")

    elif args.sub_status=="expired":
        filterusername=list(filter(lambda x:x.get("subscribed")==None,filterusername))
        log.debug(f"+expired subscribtion filter username count: {len(filterusername)}")

    filterusername=list(filter(lambda x:x["name"] not in args.excluded_username ,filterusername))
    log.debug(f"final username count with all filters: {len(filterusername)}")
    if len(filterusername)==0:
        raise Exception("You have filtered the user list to zero\nPlease Select less restrictive filters")
    return sort_models_helper(filterusername)      



def sort_models_helper(models):
    sort=args.sort
    reverse=args.desc
    if sort=="name":
        return sorted(models,reverse=reverse, key=lambda x:x["name"])
    elif sort=="expired":
        return sorted(models,reverse=reverse, key=lambda x:arrow.get(x.get("expired") or 0).float_timestamp)
    elif sort=="subscribed":
        return sorted(models,reverse=reverse, key=lambda x:arrow.get(x.get("subscribed") or 0).float_timestamp)
    elif sort=="price":
        return sorted(models,reverse=reverse, key=lambda x:x.get("price") or 0)
    else:
        return sorted(models,reverse=reverse, key=lambda x:x["name"])
#check if auth is valid
def process_me(headers):
    my_profile = me.scrape_user(headers)
    name, username = me.parse_user(my_profile)
    subscribe_count=me.parse_subscriber_count()
    me.print_user(name, username)
    return subscribe_count

def get_models(subscribe_count) -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with stdout.lowstdout():
        with Progress(  SpinnerColumn(style=Style(color="blue")),TextColumn("{task.description}")) as progress:
            task1=progress.add_task('Getting your subscriptions (this may take awhile)...')
            list_subscriptions = asyncio.run(
                subscriptions.get_subscriptions(subscribe_count))
            parsed_subscriptions = subscriptions.parse_subscriptions(
                list_subscriptions)
            progress.remove_task(task1)
            return parsed_subscriptions


def get_model(parsed_subscriptions: list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding 
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions)        