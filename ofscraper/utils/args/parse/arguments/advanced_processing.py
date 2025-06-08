import cloup as click
from ofscraper.utils.args.callbacks.arguments.username import set_search_strategy_flag


users_first_option = click.option(
    "-uf",
    "--users-first",
    "--user-first",
    "--usersfirst",
    "--userfirst",
    "users_first",
    help="Process all users first rather than one at a time (affects --action)",
    default=False,
    is_flag=True,  # Shorthand for action="store_true"
)

username_search_option = click.option(
    "-fi/-fl",
    "--username-individual-search/--username-list-search",
    "--user-individual-search/--user-list-search",
    "username_search", # The new, shared destination
    help="""
        \b
        Set the search strategy when --username is provided.
        --individual: Search each username as a separate request.
        --list: Search entire enabled lists before filtering (default).
    """,
    # The default from the callback will be used.
    # We set default=None here so the callback is triggered correctly.
    default=None,
    callback=set_search_strategy_flag,
    is_flag=True
)