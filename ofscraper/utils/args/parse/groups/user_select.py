# Create the option group
import cloup as click

from ofscraper.utils.args.parse.arguments.user_select import (
    black_list_option,
    excluded_username_option,
    user_list_option,
    usernames_option,
)

user_select_options_desc = "User Selection Options"
user_select_options_help = (
    """Specify users for scraping  with usernames, userlists, or blacklists"""
)
user_select_options_tuple = (
    usernames_option,
    excluded_username_option,
    user_list_option,
    black_list_option,
)

user_select_options = click.option_group(
    user_select_options_desc,
    *user_select_options_tuple,
    help=user_select_options_help,
)
