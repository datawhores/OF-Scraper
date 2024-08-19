import cloup as click

from ofscraper.utils.args.parse.arguments.advanced_processing import (
    individual_search_option,
    search_entire_list_option,
    users_first_option,
)

advanced_processing_desc = "Advanced Search & Processing Options"
# Create the option group with mutually exclusive constraints
advanced_processing_help = "Choose how usernames are searched, and define the order in which users are processed for actions"
advanced_processing_tuple = (
    users_first_option,
    click.constraints.mutually_exclusive(
        individual_search_option, search_entire_list_option
    ),
)
advanced_processing_options = click.option_group(
    advanced_processing_desc, *advanced_processing_tuple, help=advanced_processing_help
)
