r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""
import copy
import re

from InquirerPy.base import Choice
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.models.selector as userselector
import ofscraper.prompts.model_helpers as modelHelpers
import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.utils.args.read as read_args

console = Console()
models = None


def funct(prompt):
    oldargs = copy.deepcopy(vars(read_args.retriveArgs()))
    userselector.setfilter()
    userselector.setsort()
    if oldargs != vars(read_args.retriveArgs()):
        global models
        models = userselector.filterNSort(userselector.ALL_SUBS)
    choices = list(
        map(
            lambda x: modelHelpers.model_selectorHelper(x[0], x[1]),
            enumerate(models),
        )
    )
    selectedSet = set(
        map(
            lambda x: re.search("^[0-9]+: ([^ ]+)", x["name"]).group(1),
            prompt.selected_choices or [],
        )
    )
    for model in choices:
        name = re.search("^[0-9]+: ([^ ]+)", model.name).group(1)
        if name in selectedSet:
            model.enabled = True
    prompt.content_control._raw_choices = choices
    prompt.content_control.choices = prompt.content_control._get_choices(
        prompt.content_control._raw_choices, prompt.content_control._default
    )
    prompt.content_control._format_choices()
    return prompt


def funct2(prompt_):
    selected = prompt_.content_control.selection["value"]
    console.print(
        f"""
        Name: [bold blue]{selected.name}[/bold blue]
        ID: [bold blue]{selected.id}[/bold blue]
        Renewed Date: [bold blue]{selected.renewed_string}[/bold blue]
        Subscribed Date: [bold blue]{selected.subscribed_string}[/bold blue]
        Expired Date: [bold blue]{selected.expired_string}[/bold blue]
        Last Seen: [bold blue] {selected.last_seen_formatted}[/bold blue]
        Original Sub Price: [bold blue]{selected.sub_price}[/bold blue]     [Current Subscription Price]
        Original Regular Price: [bold blue]{selected.regular_price}[/bold blue]     [Regular Subscription Price Set By Model]
        Original Claimable Promo Price: [bold blue]{selected.lowest_promo_claim}[/bold blue]   [Lowest Promotional Price Marked as Claimable]
        Original Any Promo Price: [bold blue]{selected.lowest_promo_all}[/bold blue]     [Lowest of Any Promotional Price]
        
        ------------------------------------------------------------------------------------------------------------------------------------
        Final Current Price: [bold blue]{selected.final_current_price}[/bold blue] [Sub Price or Lowest Claimable Promo Price or Regular Price| See Final Price Details]
        Final Promo Price: [bold blue]{selected.final_promo_price}[/bold blue] [Lowest Any Promo Price or Regular Price | See Final Price Details]
        Final Renewal Price: [bold blue]{selected.final_renewal_price}[/bold blue] [Lowest Claimable Promo or Regular Price | See Final Price Details]
        Final Regular Price: [bold blue]{selected.final_regular_price}[/bold blue] [Regular Price | See Final Price Details]
        
        [italic yellow]Final Prices Detail =>[ https://of-scraper.gitbook.io/of-scraper/batch-scraping-and-bot-actions/model-selection-sorting/price-filtering-sort][/italic yellow]

        ======================================================
        
        PRESS ENTER TO RETURN
        """
    )
    prompt("")
    return prompt_


def model_selector(models_) -> bool:
    global models
    models = models_
    choices = list(
        map(lambda x: modelHelpers.model_selectorHelper(x[0], x[1]), enumerate(models))
    )

    p = promptClasses.getFuzzySelection(
        choices=choices,
        transformer=lambda result: ",".join(map(lambda x: x.split(" ")[1], result)),
        multiselect=True,
        long_instruction=prompt_strings.MODEL_SELECT,
        long_message=prompt_strings.MODEL_FUZZY,
        altx=funct,
        altd=funct2,
        validate=prompt_validators.emptyListValidator(),
        prompt="Filter: ",
        message="Which models do you want to scrape\n:",
        info=True,
    )

    return p


def decide_filters_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "input",
                "default": "No",
                "message": "Modify filters for your accounts list?\nSome usage examples are scraping free accounts only or paid accounts without renewal",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer["input"]


def modify_filters_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "renewal",
                "default": None,
                "message": "Filter account by whether it has a renewal date",
                "choices": [
                    Choice(True, "Active Only"),
                    Choice(False, "Disabled Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "expire",
                "default": None,
                "message": "Filter accounts based on access to content via a subscription",
                "choices": [
                    Choice(True, "Active Only"),
                    Choice(False, "Expired Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "last-seen",
                "default": None,
                "message": "Filter Accounts By whether the account by the visability of last seen",
                "choices": [
                    Choice(True, "Last seen is present"),
                    Choice(False, "Last seen is hidden"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "promo",
                "message": "Filter accounts presence of claimable promotions",
                "default": None,
                "choices": [
                    Choice(True, "Promotions Only"),
                    Choice(False, "No Promotions"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "all-promo",
                "message": "Filter accounts presence of any promotions",
                "default": None,
                "choices": [
                    Choice(True, "Promotions Only"),
                    Choice(False, "No Promotions"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "free-trial",
                "default": None,
                "message": "Filter Accounts By whether the account is a free trial",
                "choices": [
                    Choice(True, "Free Trial only"),
                    Choice(False, "Paid and always free accounts"),
                    Choice(None, "Any Account"),
                ],
            },
        ]
    )

    args.renewal = answer["renewal"]
    args.sub_status = answer["expire"]
    args.promo = answer["promo"]
    args.all_promo = answer["all-promo"]
    args.free_trial = answer["free-trial"]
    args.last_seen = answer["last-seen"]
    if args.free_trial != "yes":
        args = modify_current_price(args)
    if args.free_trial != "yes" and decide_price_prompt() == "Yes":
        args = modify_other_prices(args)
    return args


def modify_current_price(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "subscription",
                "message": "Filter accounts by the type of a current subscription price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Subscriptions Only"),
                    Choice("free", "Free Subscriptions Only"),
                    Choice(None, "Both"),
                ],
            },
        ]
    )

    args.current_price = answer["subscription"]
    return args


def decide_price_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "input",
                "default": "No",
                "message": "Would you like to modify other price types",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer["input"]


def modify_other_prices(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "regular",
                "message": "Filter accounts by the regular subscription price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Subscriptions Only"),
                    Choice("free", "Free Subscriptions Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "future",
                "message": "Filter accounts by renewal price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Renewals Only"),
                    Choice("free", "Free Renewals Only"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "promo-price",
                "message": "Filter accounts by any promotional price",
                "default": None,
                "choices": [
                    Choice("paid", "Paid Promotions"),
                    Choice("free", "Free Promotions"),
                    Choice(None, "Both"),
                ],
            },
        ]
    )

    args.regular_price = answer["regular"]
    args.renewal_price = answer["future"]
    args.promo_price = answer["promo-price"]
    return args


def decide_sort_prompt():
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "input",
                "message": f"Change the Order or the Criteria for how the model list is sorted\nCurrent setting are {read_args.retriveArgs().sort.capitalize()} in {'Ascending' if not read_args.retriveArgs().desc else 'Descending'} order",
                "default": "No",
                "choices": ["Yes", "No"],
            }
        ]
    )

    return answer["input"]


def modify_sort_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "type",
                "message": "Sort Accounts by..",
                "default": args.desc == False,
                "choices": [
                    Choice("name", "By Name"),
                    Choice("subscribed", "Subscribed Date"),
                    Choice("expired", "Expiring Date"),
                    Choice("last-seen", "Last Seen"),
                    Choice("current-price", "Current Price"),
                    Choice("promo-price", "Promotional Price"),
                    Choice("regular-price", "Regular Price"),
                    Choice("renewal-price", "Renewal Price"),
                ],
            },
            {
                "type": "list",
                "name": "order",
                "message": "Sort Direction",
                "choices": [
                    Choice(True, "Ascending"),
                    Choice(False, "Descending", enabled=True),
                ],
                "default": True,
            },
        ]
    )

    args.sort = answer["type"]
    args.desc = answer["order"] == False
    return args


def reset_username_prompt() -> bool:
    name = "reset username"
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Do you want to reset username info",
                "choices": [
                    Choice("Selection", "Yes Update Selection"),
                    Choice("Data", "Yes Refetch Data Only"),
                    Choice("Selection_Strict", "Yes Update Selection (No Data Fetch)"),
                    "No",
                ],
                "default": "No",
            }
        ]
    )

    return answer[name]
