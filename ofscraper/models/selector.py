import logging
import time

import ofscraper.filters.models.date as date_
import ofscraper.filters.models.flags as flags
import ofscraper.filters.models.other as other
import ofscraper.filters.models.price as price
import ofscraper.filters.models.sort as sort
import ofscraper.filters.models.subtype as subtype
import ofscraper.models.retriver as retriver
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.user as user_helper
import ofscraper.utils.args.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.manager as manager
import ofscraper.utils.settings as settings

ALL_SUBS = None
PARSED_SUBS = None
ALL_SUBS_DICT = None
log = logging.getLogger("shared")


def get_model_fromParsed(name):
    global ALL_SUBS_DICT
    return ALL_SUBS_DICT.get(name)


def set_ALL_SUBS_DICT(subsDict=None):
    global ALL_SUBS
    global ALL_SUBS_DICT
    if subsDict and isinstance(subsDict, dict):
        ALL_SUBS_DICT = subsDict
    else:
        subList = subsDict or ALL_SUBS or []
        ALL_SUBS_DICT = {}
        [ALL_SUBS_DICT.update({ele.name: ele}) for ele in subList]


def get_ALL_SUBS_DICT():
    global ALL_SUBS_DICT
    return ALL_SUBS_DICT


def set_ALL_SUBS_DICTVManger(subsDict=None):
    global ALL_SUBS_DICT
    set_ALL_SUBS_DICT(subsDict)
    manager.update_dict({"subs": ALL_SUBS_DICT})


def get_ALL_SUBS():
    global ALL_SUBS
    return ALL_SUBS


def get_ALL_SUBS_DICTVManger():
    return manager.get_manager_dict().get("subs")


def getselected_usernames(rescan=False, reset=False):
    # username list will be retrived every time resFet==True
    global ALL_SUBS
    global PARSED_SUBS
    if reset == True and rescan == True:
        all_subs_helper()
        parsed_subscriptions_helper(reset=True)
    elif reset is True and PARSED_SUBS:
        prompt = prompts.reset_username_prompt()
        if prompt == "Selection":
            all_subs_helper()
            parsed_subscriptions_helper(reset=True)
        elif prompt == "Data":
            all_subs_helper()
            parsed_subscriptions_helper()
        elif prompt == "Selection_Strict":
            parsed_subscriptions_helper(reset=True)
    elif rescan == True:
        all_subs_helper()
        parsed_subscriptions_helper()
    else:
        all_subs_helper(refetch=False)
        parsed_subscriptions_helper()
    return PARSED_SUBS


def all_subs_helper(refetch=True, main=False, check=True):
    global ALL_SUBS
    if bool(ALL_SUBS) and not refetch:
        return
    while True:
        ALL_SUBS = retriver.get_models()
        if len(ALL_SUBS) > 0 or not check:
            set_ALL_SUBS_DICTVManger(subsDict=ALL_SUBS)
            break
        elif len(ALL_SUBS) == 0:
            print("No accounts found during scan")
            # give log time to process
            time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT"))
            if not prompts.retry_user_scan():
                raise Exception("Could not find any accounts on list")


def parsed_subscriptions_helper(reset=False):
    global ALL_SUBS
    global PARSED_SUBS
    args = read_args.retriveArgs()
    if reset == True:
        args.username = None
        write_args.setArgs(args)
    if not bool(args.username):
        selectedusers = retriver.get_selected_model(filterNSort())
        read_args.retriveArgs().username = list(map(lambda x: x.name, selectedusers))
        PARSED_SUBS = selectedusers
        write_args.setArgs(args)
    elif "ALL" in args.username:
        PARSED_SUBS = filterNSort()
    elif args.username:
        usernameset = set(args.username)
        PARSED_SUBS = list(filter(lambda x: x.name in usernameset, ALL_SUBS))
    return PARSED_SUBS


def setfilter(forced=False):
    global args
    while True:
        choice = prompts.decide_filters_menu()
        if choice == "modelList":
            break
        elif choice == "sort":
            args = prompts.modify_sort_prompt(read_args.retriveArgs())
        elif choice == "subtype":
            args = prompts.modify_subtype_prompt(read_args.retriveArgs())
        elif choice == "promo":
            args = prompts.modify_promo_prompt(read_args.retriveArgs())
        elif choice == "active":
            args = prompts.modify_active_prompt(read_args.retriveArgs())
        elif choice == "price":
            args = prompts.modify_prices_prompt(read_args.retriveArgs())
        elif choice == "reset":
            old_args = read_args.retriveArgs()
            old_blacklist = old_args.black_list
            old_list = old_args.user_list
            args = user_helper.resetUserFilters()
            if not list(sorted(old_blacklist)) == list(
                sorted(args.black_list)
            ) or not list(sorted(old_list)) == list(sorted(args.user_list)):
                print("Updating Models")
                all_subs_helper(check=False)
        elif choice == "list":
            old_args = read_args.retriveArgs()
            old_blacklist = old_args.black_list
            old_list = old_args.user_list
            args = prompts.modify_list_prompt(old_args)
            if not list(sorted(old_blacklist)) == list(
                sorted(args.black_list)
            ) or not list(sorted(old_list)) == list(sorted(args.user_list)):
                print("Updating Models")
                all_subs_helper(check=False)
        write_args.setArgs(args)


def filterNSort():
    global ALL_SUBS
    while True:
        # paid/free
        usernames = ALL_SUBS

        log.debug(f"username count no filters: {len(usernames)}")
        filterusername = filterOnly(usernames)
        log.debug(f"final username count with all filters: {len(filterusername)}")
        # give log time to process
        time.sleep(constants.getattr("LOG_DISPLAY_TIMEOUT"))
        if len(filterusername) != 0:
            return sort.sort_models_helper(filterusername)
        print(
            f"""You have filtered the user list to zero
Change the filter settings to continue

Active userlist : {settings.get_userlist() or 'no blacklist'}
Active blacklist : {settings.get_blacklist() or 'no userlist'}

Sub Status: {read_args.retriveArgs().sub_status or 'No Filter'}
Renewal Status: {read_args.retriveArgs().renewal or 'No Filter'}

Promo Price Filter: {read_args.retriveArgs().promo_price or 'No Filter'}
Current Price Filter: {read_args.retriveArgs().current_price or 'No Filter'}
Current Price Filter: {read_args.retriveArgs().current_price or 'No Filter'}
Renewal Price Filter: {read_args.retriveArgs().renewal_price or 'No Filter'}

[ALT+D] More Filters

"""
        )

        setfilter(forced=True)


def filterOnly(usernames=None):
    usernames = usernames or ALL_SUBS
    filterusername = subtype.subType(usernames)
    filterusername = price.pricePaidFreeFilterHelper(filterusername)
    filterusername = flags.promoFilterHelper(filterusername)
    filterusername = date_.dateFilters(filterusername)
    filterusername = other.otherFilters(filterusername)
    return filterusername
