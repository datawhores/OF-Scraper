import itertools
import re

import cloup as click

import ofscraper.utils.args.helpers.type as type

usernames_option = click.option(
    "-u",
    "--usernames",
    "--username",
    # "username",  # Comment out if not needed
    help="Select which username to process (name,name2). Set to ALL for all users",
    default=None,
    type=type.username_helper,  # Assuming you'll still use this helper function
    multiple=True,  # Use `multiple=True` for accepting multiple values
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
)

excluded_username_option = click.option(
    "-eu",
    "--excluded-username",
    help="Select which usernames to exclude (name,name2). Has preference over --username",
    type=type.username_helper,
    default=None,
    multiple=True,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
)

user_list_option = click.option(
    "-ul",
    "user_list",
    "--user-list",
    "--userlist",
    "--userlists",
    "--user-lists",
    help="Filter by userlist. Note: the lists 'ofscraper.main', 'ofscraper.expired', and 'ofscraper.active' are reserved and should not be the name of any list you have on OF",
    default=None,
    multiple=True,
    callback=lambda ctx, param, value: list(
        set(
            itertools.chain.from_iterable(
                [
                    (re.split(r"[,]+", item.lower()) if isinstance(item, str) else item)
                    for item in value
                ]
            )
        )
        if value
        else []
    ),
)

black_list_option = click.option(
    "-bl",
    "black_list",
    "--black-lists",
    "--blacklist",
    "--blacklists",
    "--black-list",
    help="Remove all users from selected list. Note: the lists 'ofscraper.main', 'ofscraper.expired', and 'ofscraper.active' are reserved and should not be the name of any list you have on OF",
    default=None,
    multiple=True,
    callback=lambda ctx, param, value: list(
        set(
            itertools.chain.from_iterable(
                [
                    (
                        re.split(r"[,\s]+", item.lower())
                        if isinstance(item, str)
                        else item
                    )
                    for item in value
                ]
            )
        )
        if value
        else []
    ),
)

# Create the option group

user_select_options = click.option_group(
    "User Selection Options",
    usernames_option,
    excluded_username_option,
    user_list_option,
    black_list_option,
    help="""Specify users for scraping  with usernames, userlists, or blacklists""",
)
