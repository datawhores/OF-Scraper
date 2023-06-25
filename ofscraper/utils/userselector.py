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


selectedusers=None
log=logging.getLogger(__package__)
args=args_.getargs()

def getselected_usernames():
    #username list will be retrived once per daemon run
    # manual prompt will need to recertify options every call
    global selectedusers
    scraper_bool=len(args.posts)>0 or args.action
    #always return with correct args
    if "Skip" in args.posts:
        return []
    if selectedusers and scraper_bool:
            return selectedusers
    if scraper_bool:
        selectedusers=selectuserhelper()
    #create in these situations
    #set at least once
    elif args.username and not selectedusers:
        selectedusers=selectuserhelper()
    elif not selectedusers and not scraper_bool:
        selectedusers=selectuserhelper()
    elif selectedusers and not scraper_bool:
        if prompts.reset_username_prompt()=="Yes":  
            selectedusers=selectuserhelper()
    return selectedusers

def selectuserhelper():
    headers = auth.make_headers(auth.read_auth())
    subscribe_count = process_me(headers)
    parsed_subscriptions = get_models(headers, subscribe_count)
    if args.username and "ALL" in args.username:
        filter_subscriptions=filterNSort(parsed_subscriptions )
        selectedusers=filter_subscriptions
        
    elif args.username:
        selectedusers=list(filter(lambda x:x["name"] in args.username,parsed_subscriptions))
    #manually select usernames
    else:
        selected=None
        while True:
            filter_subscriptions=filterNSort(parsed_subscriptions)
            selectedusers,p= get_model(filter_subscriptions,selected)
            if selectedusers!=None:
                break

            setfilter()
            setsort()
            selected=p.selected_choices
    return selectedusers or []



        

        

 
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
    log.debug(f"Init username length: {len(filterusername)}")
    dateNow=arrow.now()
    if args.account_type=="paid":
        filterusername=list(filter(lambda x:(x.get("price") or 0)>0,filterusername))
        log.debug(f"+paid filter username length: {len(filterusername)}")

    elif args.account_type=="free":
        filterusername=list(filter(lambda x:(x.get("price") or 0)==0,filterusername))    
        log.debug(f"+free filter username length: {len(filterusername)}")
    
    if args.renewal=="active":
        filterusername=list(filter(lambda x:x.get("renewed")!=None,filterusername))
        log.debug(f"+active renewal filter username length: {len(filterusername)}")

    elif args.renewal=="disabled":
        filterusername=list(filter(lambda x:x.get("renewed")==None,filterusername))  
        log.debug(f"+disabled renewal filter username length: {len(filterusername)}")

    if args.sub_status=="active":
        filterusername=list(filter(lambda x:x.get("subscribed")!=None,filterusername)) 
        log.debug(f"+active subscribtion filter username length: {len(filterusername)}")

    elif args.sub_status=="expired":
        filterusername=list(filter(lambda x:x.get("subscribed")==None,filterusername))
        log.debug(f"+expired subscribtion filter username length: {len(filterusername)}")

    filterusername=list(filter(lambda x:x["name"] not in args.excluded_username ,filterusername))
    log.debug(f"final length with all filters: {len(filterusername)}")
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
    subscribe_count=me.parse_subscriber_count(headers)
    me.print_user(name, username)
    return subscribe_count

def get_models(headers, subscribe_count) -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with stdout.lowstdout():
        with Progress(  SpinnerColumn(style=Style(color="blue")),TextColumn("{task.description}")) as progress:
            task1=progress.add_task('Getting your subscriptions (this may take awhile)...')
            list_subscriptions = asyncio.run(
                subscriptions.get_subscriptions(headers, subscribe_count))
            parsed_subscriptions = subscriptions.parse_subscriptions(
                list_subscriptions)
            progress.remove_task(task1)
            return parsed_subscriptions


def get_model(parsed_subscriptions: list,selected) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding 
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions,selected)        