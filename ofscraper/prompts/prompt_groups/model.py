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

import inspect

import arrow
from InquirerPy.base import Choice
from InquirerPy.separator import Separator
from prompt_toolkit.shortcuts import prompt as prompt
from rich.console import Console

import ofscraper.prompts.prompt_strings as prompt_strings
import ofscraper.prompts.prompt_validators as prompt_validators
import ofscraper.prompts.promptConvert as promptClasses
import ofscraper.prompts.utils.model_helpers as modelHelpers
import ofscraper.prompts.utils.prompt_helpers as prompt_helpers
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants

console = Console()
models = None


def model_selector(models_) -> bool:
    global models
    models = models_
    choices = list(
        map(lambda x: modelHelpers.model_selectorHelper(x[0], x[1]), enumerate(models.values()))
    )

    p = promptClasses.getFuzzySelection(
        choices=choices,
        transformer=lambda result: ",".join(map(lambda x: x.split(" ")[1], result)),
        multiselect=True,
        more_instruction=prompt_strings.MODEL_SELECT,
        long_message=prompt_strings.MODEL_FUZZY,
        altx=prompt_helpers.model_funct,
        altd=prompt_helpers.model_details,
        validate=prompt_validators.emptyListValidator(),
        additional_keys={"Alt-B": prompt_helpers.model_select_funct},
        prompt="Filter: ",
        message="Which models do you want to scrape\n:",
        info=True,
    )

    return p


def decide_filters_menu() -> int:
    name = "modelList"
    modelChoice = [*constants.getattr("modelPrompt")]
    modelChoice.insert(4, Separator())
    modelChoice.insert(7, Separator())
    modelChoice.insert(9, Separator())
    questions = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": name,
                "message": "Make changes to model list",
                "choices": modelChoice,
            }
        ],
        altd=prompt_helpers.get_current_filters,
        more_instructions=prompt_strings.FILTER_DETAILS,
    )

    return constants.getattr("modelPrompt").get(questions[name])


def modify_subtype_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "renewal",
                "default": (
                    True
                    if read_args.retriveArgs().renewal
                    else False if read_args.retriveArgs().renewal is False else None
                ),
                "message": "Filter account by whether it has a renewal date",
                "choices": [
                    Choice(True, "Renewal On"),
                    Choice(False, "Renewal Off"),
                    Choice(None, "Both"),
                ],
            },
            {
                "type": "list",
                "name": "expire",
                "default": (
                    True
                    if read_args.retriveArgs().sub_status
                    else False if read_args.retriveArgs().sub_status is False else None
                ),
                "message": "Filter accounts based on access to content via a subscription",
                "choices": [
                    Choice(True, "Active Only"),
                    Choice(False, "Expired Only"),
                    Choice(None, "Both"),
                ],
            },
        ]
    )

    args.renewal = answer["renewal"]
    args.sub_status = answer["expire"]
    return args


def modify_active_prompt(args):
    answer = promptClasses.batchConverter(
        *[
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
                "type": "input",
                "name": "last-seen-after",
                "message": "Filter accounts by last seen being after the given date",
                "option_instruction": """enter 0 to disable this filter
                Otherwise must be in date format
                """,
                "validate": prompt_validators.datevalidator(),
                "filter": lambda x: arrow.get(x or 0),
                "default": (
                    arrow.get(read_args.retriveArgs().last_seen_after).format(
                        constants.getattr("PROMPT_DATE_FORMAT")
                    )
                    if read_args.retriveArgs().last_seen_after
                    else ""
                ),
            },
            {
                "type": "input",
                "name": "last-seen-before",
                "message": "Filter accounts by last seen being before the given date",
                "option_instruction": """enter 0 to disable this filter
                Otherwise must be in date format""",
                "validate": prompt_validators.datevalidator(),
                "filter": lambda x: arrow.get(x or 0),
                "default": (
                    arrow.get(read_args.retriveArgs().last_seen_before).format(
                        constants.getattr("PROMPT_DATE_FORMAT")
                    )
                    if read_args.retriveArgs().last_seen_before
                    else ""
                ),
            },
        ],
        more_instructions="""
        \n
        --last-seen filters by visiblity of 'last seen' value
        in contrast to [--last-seen-after/--last-seen-before]
        which both use a the current time if model hides 'last seen'""",
    )

    args.last_seen = answer["last-seen"]
    args.last_seen_after = (
        answer["last-seen-after"] if answer["last-seen-after"] != arrow.get(0) else None
    )
    args.last_seen_before = (
        answer["last-seen-before"]
        if answer["last-seen-before"] != arrow.get(0)
        else None
    )
    return args


def modify_promo_prompt(args):
    answer = {}
    if (
        args.current_price is not None
        or args.promo_price is not None
        or args.regular_price is not None
    ):
        console.print(
            inspect.cleandoc(
                """
                      [bold yellow]Please consider disabling price filters
                      or changing 'free trial' to 'Any Account' to prevent filtering model list to zero[/bold yellow]"""
            )
        )

    free_trail = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "free-trial",
                "default": (
                    True
                    if read_args.retriveArgs().free_trial is True
                    else False if read_args.retriveArgs().free_trial is False else None
                ),
                "message": "Filter Accounts By whether the account is a free trial",
                "choices": [
                    Choice(True, "Free Trial only"),
                    Choice(False, "Paid and always free accounts"),
                    Choice(None, "Any Account"),
                ],
            },
        ]
    )
    if free_trail["free-trial"]:
        console.print(
            inspect.cleandoc(
                """
                      [bold yellow]Setting both promos types to false is not allowed since 'Free Trial' is True and requires a promo[/bold yellow]"""
            )
        )
        promo = promptClasses.batchConverter(
            *[
                {
                    "type": "list",
                    "name": "promo",
                    "message": "Which kind of promo(s) do you want to enable",
                    "default": (
                        True
                        if read_args.retriveArgs().promo
                        else False if read_args.retriveArgs().promo is False else None
                    ),
                    "choices": [
                        Choice({"all_promo": True, "promo": True}, "Any Promo"),
                        Choice(
                            {"all_promo": None, "promo": True}, "Claimable Promo Only"
                        ),
                    ],
                },
            ]
        )["promo"]
    else:
        console.print(
            inspect.cleandoc(
                """
                      [bold yellow]Free Trial is not True so any promo status is allowed[/bold yellow]"""
            )
        )

        promo_type = promptClasses.batchConverter(
            *[
                {
                    "type": "list",
                    "name": "promo",
                    "message": "Which Promo Type do you want to change",
                    "choices": [
                        Choice("all_promo", "Any Promotions"),
                        Choice("promo", "Claimable Promotions"),
                    ],
                },
            ]
        )["promo"]
        promo = promptClasses.batchConverter(
            *[
                {
                    "type": "list",
                    "name": promo_type,
                    "message": f"Filter accounts presence of {'Any Promotions' if promo_type=='all_promo' else 'Claimable Promotions'}",
                    "default": (
                        True
                        if read_args.retriveArgs()[promo_type]
                        else (
                            False
                            if read_args.retriveArgs()[promo_type] is False
                            else None
                        )
                    ),
                    "choices": [
                        Choice(True, "Promotions Only"),
                        Choice(False, "No Promotions"),
                        Choice(None, "Both"),
                    ],
                },
            ]
        )

    answer.update(free_trail)
    args.free_trial = answer["free-trial"]
    args.update(promo)

    return args


def modify_prices_prompt(args):
    if args.free_trial:
        console.print(
            inspect.cleandoc(
                """
            [bold yellow]Free trial is True
            To avoid filtering list to zero
            Regular Subscription Price must be set to 'Paid/Both'
            Current or Promo  Subscription Price must be 'Free/Both'[/bold yellow]
            """
            )
        )
    elif args.free_trial is False:
        console.print(
            inspect.cleandoc(
                """
            [bold yellow]Free trial is False
            To avoid filtering list to zero
            Regular Subscription Price must be 'Free/Both' or
            Current and Promo  Subscription Price must be'Paid/Both'[/bold yellow]
            """
            )
        )
    price_type = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "price",
                "message": "Which price do you want to modify",
                "default": None,
                "choices": [
                    Choice("current_price", "Current Subscription Price"),
                    Choice("regular_price", "Regular Subscription Price"),
                    Choice("promo_price", "Promo Subscription Price"),
                    Choice("renewal_price", "Renewal Subscription Price"),
                ],
            },
        ],
        altd=prompt_helpers.price_info,
        more_instruction=prompt_strings.PRICE_DETAILS,
    )
    args[price_type["price"]]

    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "price",
                "message": f"Filter accounts by {price_type['price'].title().replace('_',' ')}",
                "default": args[price_type["price"]],
                "choices": [
                    Choice("paid", "Paid Subscriptions Only"),
                    Choice("free", "Free Subscriptions Only"),
                    Choice(None, "Both"),
                ],
            },
        ],
        altd=prompt_helpers.price_info,
        more_instruction=prompt_strings.PRICE_DETAILS,
    )
    args[price_type["price"]] = answer["price"]
    return args


def modify_sort_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "list",
                "name": "type",
                "message": "Sort Accounts by..",
                "default": args.desc is False,
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
        ],
        altd=prompt_helpers.sort_info,
        more_instruction=prompt_strings.SORT_DETAILS,
    )

    args.sort = answer["type"]
    args.desc = answer["order"] is False
    return args


def modify_list_prompt(args):
    answer = promptClasses.batchConverter(
        *[
            {
                "type": "input",
                "name": "user_list",
                "message": "Change User List",
                "default": ",".join(args.user_list or []),
                "multiline": True,
                "filter": lambda x: prompt_helpers.user_list(x),
                "option_instruction": prompt_helpers.get_list_details(True),
            },
            {
                "type": "input",
                "name": "black_list",
                "message": "Change Black List",
                "default": ",".join(args.black_list or []),
                "multiline": True,
                "filter": lambda x: prompt_helpers.user_list(x),
                "option_instruction": prompt_helpers.get_list_details(False),
            },
        ],
    )
    args.user_list = list(answer["user_list"])
    args.black_list = list(answer["black_list"])
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
