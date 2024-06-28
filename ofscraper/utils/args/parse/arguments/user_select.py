import itertools
import re

import cloup as click

from ofscraper.utils.args.callbacks.username import UsernameParse

usernames_option = click.option(
    "-u",
    "--usernames",
    "--username",
    # "username",  # Comment out if not needed
    help="Select which username to process (name,name2). Set to ALL for all users",
    default=None,
    multiple=True,  # Use `multiple=True` for accepting multiple values
    callback=UsernameParse,
)

excluded_username_option = click.option(
    "-eu",
    "--excluded-username",
    help="Select which usernames to exclude (name,name2). Has preference over --username",
    default=None,
    multiple=True,
    callback=UsernameParse,
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
