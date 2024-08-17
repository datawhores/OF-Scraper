# Create the option group
import cloup as click

from ofscraper.utils.args.parse.arguments.user_sort import (
    sort_by_option,
    sort_descending_option,
)

user_sorting_options_desc = "Model Sort & Processing Order Options"
user_sorting_options_help = """Define the order in which models are displayed and processed for actions like liking posts, downloading content, or data gathering"""
user_sorting_options_tuple = (sort_by_option, sort_descending_option)
user_sorting_options = click.option_group(
    user_sorting_options_desc,
    *user_sorting_options_tuple,
    help=user_sorting_options_help
)
