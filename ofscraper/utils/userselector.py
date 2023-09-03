import asyncio
import logging
import arrow
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args as args_
import ofscraper.api.subscriptions as subscriptions
import ofscraper.api.lists as lists
import ofscraper.api.me as me
import ofscraper.utils.args as args_
import ofscraper.utils.stdout as stdout





ALL_SUBS=None
PARSED_SUBS=None
log=logging.getLogger("shared")


def getselected_usernames(rescan=False,reset=False):
    #username list will be retrived every time reset==True
    global ALL_SUBS
    global PARSED_SUBS

    if "Skip" in args_.getargs().posts:
        return []
    if reset==True and PARSED_SUBS:
        if prompts.reset_username_prompt()=="Yes":
           PARSED_SUBS=None
           args_.getargs().username=None
           args_.changeargs(args)
    if rescan==True:
        PARSED_SUBS=None
    if not PARSED_SUBS or not args_.getargs().username:
        all_subs_helper()
        parsed_subscriptions_helper()
    return PARSED_SUBS


 
    
def all_subs_helper(): 
    global ALL_SUBS
    ALL_SUBS= get_models()


def parsed_subscriptions_helper(force=False):
    global ALL_SUBS
    global PARSED_SUBS
    global args
    args= args_.getargs()
    if not args_.getargs().username:
        selectedusers=get_model(filterNSort((ALL_SUBS)))
        args_.getargs().username=list(map(lambda x:x["name"],selectedusers))
        PARSED_SUBS=selectedusers
        args_.changeargs(args)  
    elif "ALL" in args_.getargs().username:
        PARSED_SUBS=filterNSort(ALL_SUBS)
    elif args_.getargs().username:
        usernameset=set(args_.getargs().username)
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
    if args_.getargs().account_type=="paid":
        filterusername=list(filter(lambda x:(x.get("price") or 0)>0,filterusername))
        log.debug(f"+paid filter username count: {len(filterusername)}")

    elif args_.getargs().account_type=="free":
        filterusername=list(filter(lambda x:(x.get("price") or 0)==0,filterusername))    
        log.debug(f"+free filter username count: {len(filterusername)}")
    
    if args_.getargs().renewal=="active":
        filterusername=list(filter(lambda x:x.get("renewed")!=None,filterusername))
        log.debug(f"+active renewal filter username count: {len(filterusername)}")

    elif args_.getargs().renewal=="disabled":
        filterusername=list(filter(lambda x:x.get("renewed")==None,filterusername))  
        log.debug(f"+disabled renewal filter username count: {len(filterusername)}")

    if args_.getargs().sub_status=="active":
        filterusername=list(filter(lambda x:x.get("subscribed")!=None,filterusername)) 
        log.debug(f"+active subscribtion filter username count: {len(filterusername)}")

    elif args_.getargs().sub_status=="expired":
        filterusername=list(filter(lambda x:x.get("subscribed")==None,filterusername))
        log.debug(f"+expired subscribtion filter username count: {len(filterusername)}")

    filterusername=list(filter(lambda x:x["name"] not in args_.getargs().excluded_username ,filterusername))
    log.debug(f"final username count with all filters: {len(filterusername)}")
    if len(filterusername)==0:
        raise Exception("You have filtered the user list to zero\nPlease Select less restrictive filters and userlists")
    return sort_models_helper(filterusername)      



def sort_models_helper(models):
    sort=args_.getargs().sort
    reverse=args_.getargs().desc
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
def process_me():
    my_profile = me.scrape_user()
    name, username = me.parse_user(my_profile)
    subscribe_count=me.parse_subscriber_count()
    me.print_user(name, username)
    return subscribe_count

def get_models() -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with stdout.lowstdout():
        count=process_me()
        out=[]
        active_subscriptions = subscriptions.get_subscriptions(count[0])
        expired_subscriptions=subscriptions.get_subscriptions(count[1],account="expired")
        other_subscriptions=lists.get_otherlist()
        out.extend(active_subscriptions)
        out.extend(expired_subscriptions)
        out.extend(other_subscriptions)
        black_list=lists.get_blacklist()
        out=list(filter(lambda x:x.get("id") not in black_list,out))
        parsed_subscriptions = subscriptions.parse_subscriptions(
            out)
        return parsed_subscriptions


def get_model(parsed_subscriptions: list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding 
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions)        