import cloup as click
from ofscraper.utils.args.parse.arguments.advanced_processing import users_first_option,individual_search_option,search_entire_list_option
# Create the option group with mutually exclusive constraints
advanced_processing_options = click.option_group(
    "Advanced Search & Processing Options",
    users_first_option,
    click.constraints.mutually_exclusive(
        individual_search_option, search_entire_list_option
    ),
    help="Choose how usernames are searched, and define the order in which users are processed for actions",
)