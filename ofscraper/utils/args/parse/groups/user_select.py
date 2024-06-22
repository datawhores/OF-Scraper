# Create the option group
import cloup as click
from ofscraper.utils.args.parse.arguments.user_select import user_list_option,usernames_option,black_list_option,excluded_username_option

user_select_options = click.option_group(
    "User Selection Options",
    usernames_option,
    excluded_username_option,
    user_list_option,
    black_list_option,
    help="""Specify users for scraping  with usernames, userlists, or blacklists""",
)
