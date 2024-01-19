import logging
import time

import ofscraper.filters.models.date as date_
import ofscraper.filters.models.flags as flags
import ofscraper.filters.models.other as other
import ofscraper.filters.models.price as price
import ofscraper.filters.models.retriver as retriver
import ofscraper.filters.models.sort as sort
import ofscraper.filters.models.subtype as subtype
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.constants as constants

ALL_SUBS = None
PARSED_SUBS = None
log = logging.getLogger("shared")


def get_model_fromParsed(name):
    modelObjs = list(filter(lambda x: x.name == name, PARSED_SUBS))
    return modelObjs[0] if len(modelObjs) > 0 else None


def getselected_usernames(rescan=False, reset=False):
    # username list will be retrived every time resFet==True
    global ALL_SUBS
    global PARSED_SUBS
    if reset is True and PARSED_SUBS:
        prompt = prompts.reset_username_prompt()
        if prompt == "Selection":
            PARSED_SUBS = None
            global_args.getArgs().username = None
            args_.changeargs(args)
        if prompt == "No":
            rescan = False
    if rescan is True:
        PARSED_SUBS = None
    if not PARSED_SUBS or not global_args.getArgs().username:
        all_subs_helper()
        parsed_subscriptions_helper()
    return PARSED_SUBS


def all_subs_helper():
    global ALL_SUBS
    while True:
        ALL_SUBS = retriver.get_models()
        if len(ALL_SUBS) > 0:
            return
        elif len(ALL_SUBS) == 0:
            print("No accounts found during scan")
            # give log time to process
            time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT"))
            if not prompts.retry_user_scan():
                raise Exception("Could not find any accounts on list")


def parsed_subscriptions_helper(force=False):
    global ALL_SUBS
    global PARSED_SUBS
    global args
    args = global_args.getArgs()
    if not global_args.getArgs().username:
        selectedusers = retriver.get_model(filterNSort((ALL_SUBS)))
        global_args.getArgs().username = list(map(lambda x: x.name, selectedusers))
        PARSED_SUBS = selectedusers
        args_.changeargs(args)
    elif "ALL" in global_args.getArgs().username:
        PARSED_SUBS = filterNSort(ALL_SUBS)
    elif global_args.getArgs().username:
        usernameset = set(global_args.getArgs().username)
        PARSED_SUBS = list(filter(lambda x: x.name in usernameset, ALL_SUBS))

    return PARSED_SUBS


def setfilter(forced=False):
    if forced or prompts.decide_filters_prompt() == "Yes":
        global args
        args = prompts.modify_filters_prompt(args)


def setsort(forced=False):
    if forced or prompts.decide_sort_prompt() == "Yes":
        global args
        args = prompts.modify_sort_prompt(args)


def filterNSort(usernames):
    while True:
        # paid/free
        log.debug(f"username count no filters: {len(usernames)}")
        filterusername = subtype.subType(usernames)
        filterusername = price.pricePaidFreeFilterHelper(filterusername)
        filterusername = flags.promoFilterHelper(filterusername)
        filterusername = date_.dateFilters(filterusername)
        filterusername = other.otherFilters(filterusername)

        log.debug(f"final username count with all filters: {len(filterusername)}")
        # give log time to process
        time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT"))
        if len(filterusername) != 0:
            return sort.sort_models_helper(filterusername)
        print(
            f"""You have filtered the user list to zero
Change the filter settings to continue

Sub Status: {global_args.getArgs().sub_status or 'No Filter'}
Renewal Status: {global_args.getArgs().renewal or 'No Filter'}
Promo Price Filter: {global_args.getArgs().promo_price or 'No Filter'}
Current Price Filter: {global_args.getArgs().current_price or 'No Filter'}
Current Price Filter: {global_args.getArgs().current_price or 'No Filter'}
Renewal Price Filter: {global_args.getArgs().renewal_price or 'No Filter'}
"""
        )

        setfilter(forced=True)
