import logging
import time

import arrow

import ofscraper.api.lists as lists
import ofscraper.api.me as me
import ofscraper.api.subscriptions as subscriptions
import ofscraper.constants as constants
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.args as args_
import ofscraper.utils.console as console
import ofscraper.utils.stdout as stdout

ALL_SUBS = None
PARSED_SUBS = None
log = logging.getLogger("shared")


def getselected_usernames(rescan=False, reset=False):
    # username list will be retrived every time reset==True
    global ALL_SUBS
    global PARSED_SUBS

    if "Skip" in args_.getargs().posts:
        return []
    if reset == True and PARSED_SUBS:
        if prompts.reset_username_prompt() == "Yes":
            PARSED_SUBS = None
            args_.getargs().username = None
            args_.changeargs(args)
    if rescan == True:
        PARSED_SUBS = None
    if not PARSED_SUBS or not args_.getargs().username:
        all_subs_helper()
        parsed_subscriptions_helper()

    return PARSED_SUBS


def all_subs_helper():
    global ALL_SUBS
    while True:
        ALL_SUBS = get_models()
        if len(ALL_SUBS) > 0:
            return
        elif len(ALL_SUBS) == 0:
            print("No accounts found during scan")
            # give log time to process
            time.sleep(constants.LOG_DISPLAY_TIMEOUT)
            if not prompts.retry_user_scan():
                raise Exception("Could not find any accounts on list")


def parsed_subscriptions_helper(force=False):
    global ALL_SUBS
    global PARSED_SUBS
    global args
    args = args_.getargs()
    if not args_.getargs().username:
        selectedusers = get_model(filterNSort((ALL_SUBS)))
        args_.getargs().username = list(map(lambda x: x["name"], selectedusers))
        PARSED_SUBS = selectedusers
        args_.changeargs(args)
    elif "ALL" in args_.getargs().username:
        PARSED_SUBS = filterNSort(ALL_SUBS)
    elif args_.getargs().username:
        usernameset = set(args_.getargs().username)
        PARSED_SUBS = list(filter(lambda x: x["name"] in usernameset, ALL_SUBS))

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
        filterusername = baseFilter(usernames)
        filterusername = priceFilterHelper(filterusername)
        filterusername = promoFilterHelper(filterusername)
        filterusername = list(
            filter(
                lambda x: x["name"] not in args_.getargs().excluded_username,
                filterusername,
            )
        )

        log.debug(f"final username count with all filters: {len(filterusername)}")
        # give log time to process
        time.sleep(constants.LOG_DISPLAY_TIMEOUT)
        if len(filterusername) != 0:
            return sort_models_helper(filterusername)
        print(
            f"""You have filtered the user list to zero
Change the filter settings to continue

Sub Status: {args_.getargs().sub_status or 'No Filter'}
Renewal Status: {args_.getargs().renewal or 'No Filter'}
Account Type: {args_.getargs().account_type or 'No Filter'}

"""
        )

        setfilter(forced=True)


def baseFilter(filterusername):
    log.debug(f"Renewal: {args_.getargs().renewal}")
    if args_.getargs().renewal == "active":
        filterusername = list(
            filter(lambda x: x.get("renewed") is not None, filterusername)
        )
        log.debug(f"active renewal filter username count: {len(filterusername)}")
    elif args_.getargs().renewal == "disabled":
        filterusername = list(
            filter(lambda x: x.get("renewed") == None, filterusername)
        )
        log.debug(f"disabled renewal filter username count: {len(filterusername)}")
    log.debug(f"Sub Status: {args_.getargs().sub_status}")
    if args_.getargs().sub_status == "active":
        filterusername = list(
            filter(lambda x: x.get("subscribed") is not None, filterusername)
        )
        log.debug(f"active subscribtion filter username count: {len(filterusername)}")

    elif args_.getargs().sub_status == "expired":
        filterusername = list(
            filter(lambda x: x.get("subscribed") == None, filterusername)
        )
        log.debug(f"expired subscribtion filter username count: {len(filterusername)}")
    return filterusername


def priceFilterHelper(filterusername):
    log.debug(f"Current Price Filter: {args_.getargs().current_price}")
    if args_.getargs().current_price == "paid":
        filterusername = list(
            filter(
                lambda x: x["final-current-price"] > 0,
                filterusername,
            )
        )
        log.debug(f"currently paid filter username count: {len(filterusername)}")
    elif args_.getargs().current_price == "free":
        filterusername = list(
            filter(
                lambda x: x["final-current-price"] == 0,
                filterusername,
            )
        )
        log.debug(f"currently free filter username count: {len(filterusername)}")
    log.debug(f"Account Renewal Price Filter: {args_.getargs().renewal_price}")
    if args_.getargs().renewal_price == "paid":
        filterusername = list(
            filter(
                lambda x: x["final-renewal-price"] > 0,
                filterusername,
            ),
        )

        log.debug(f"paid renewal filter username count: {len(filterusername)}")
    elif args_.getargs().renewal_price == "free":
        filterusername = list(
            filter(
                lambda x: x["final-renewal-price"] == 0,
                filterusername,
            )
        )
        log.debug(f"free renewal filter username count: {len(filterusername)}")

    log.debug(f"Regular Price Filter: {args_.getargs().regular_price}")
    if args_.getargs().regular_price == "paid":
        filterusername = list(
            filter(lambda x: x["final-regular-price"], filterusername)
        )
        log.debug(f"paid regular price filter username count: {len(filterusername)}")
    elif args_.getargs().regular_price == "free":
        filterusername = list(
            filter(lambda x: x["final-regular-price"]), filterusername
        )
        log.debug(f"free regular price filter username count: {len(filterusername)}")
    log.debug(f"Promo Price Filter: {args_.getargs().promo_price}")
    if args_.getargs().promo_price == "paid":
        filterusername = list(
            filter(
                lambda x: x["final-promo-price"] > 0,
                filterusername,
            )
        )

        log.debug(f"paid promo filter username count: {len(filterusername)}")
    elif args_.getargs().promo_price == "free":
        filterusername = list(
            filter(
                lambda x: x["final-promo-price"] == 0,
                filterusername,
            )
        )
        log.debug(f"free promo filter username count: {len(filterusername)}")
    return filterusername


def promoFilterHelper(filterusername):
    log.debug(f"Promo Price: {args_.getargs().promo}")
    if args_.getargs().promo == "yes":
        filterusername = list(
            filter(lambda x: x.get("promo-price") is not None, filterusername)
        )
    elif args_.getargs().promo == "no":
        filterusername = list(
            filter(lambda x: x.get("promo-price") is None, filterusername)
        )
    log.debug(f"All Promo Price: {args_.getargs().all_promo}")
    if args_.getargs().all_promo == "yes":
        filterusername = list(
            filter(lambda x: x.get("all-promo-price") is not None, filterusername)
        )
    elif args_.getargs().all_promo == "no":
        filterusername = list(
            filter(lambda x: x.get("all-promo-price") is None, filterusername)
        )
    return filterusername


def sort_models_helper(models):
    sort = args_.getargs().sort
    reverse = args_.getargs().desc
    if sort == "name":
        return sorted(models, reverse=reverse, key=lambda x: x["name"])
    elif sort == "expired":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: arrow.get(x.get("expired") or 0).float_timestamp,
        )
    elif sort == "subscribed":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: arrow.get(x.get("subscribed") or 0).float_timestamp,
        )
    elif sort == "current-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x["final-current-price"],
        )
    elif sort == "promo-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x["final-promo-price"],
        )

    elif sort == "renewal-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x["final-renewal-price"],
        )

    elif sort == "regular-price":
        return sorted(models, reverse=reverse, key=lambda x: x["final-regular-price"])
    else:
        return sorted(models, reverse=reverse, key=lambda x: x["name"])


# check if auth is valid
def process_me():
    my_profile = me.scrape_user()
    name, username = me.parse_user(my_profile)
    subscribe_count = me.parse_subscriber_count()
    me.print_user(name, username)
    return subscribe_count


def get_models() -> list:
    """
    Get user's subscriptions in form of a list.
    """
    with stdout.lowstdout():
        count = process_me()
        out = []
        active_subscriptions = subscriptions.get_subscriptions(count[0])
        expired_subscriptions = subscriptions.get_subscriptions(
            count[1], account="expired"
        )
        console.get_shared_console().print(
            "[yellow]Warning: Numbering on OF site can be iffy\nExample Including deactived accounts in expired\nSee: https://of-scraper.gitbook.io/of-scraper/faq#number-of-users-doesnt-match-account-number[/yellow]"
        )

        other_subscriptions = lists.get_otherlist()
        out.extend(active_subscriptions)
        out.extend(expired_subscriptions)
        out.extend(other_subscriptions)
        black_list = lists.get_blacklist()
        out = list(filter(lambda x: x.get("id") not in black_list, out))
        parsed_subscriptions = subscriptions.parse_subscriptions(out)
        return parsed_subscriptions


def get_model(parsed_subscriptions: list) -> tuple:
    """
    Prints user's subscriptions to console and accepts input from user corresponding
    to the model(s) whose content they would like to scrape.
    """
    return prompts.model_selector(parsed_subscriptions)
