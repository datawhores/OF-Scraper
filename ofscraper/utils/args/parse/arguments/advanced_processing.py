import cloup as click

users_first_option = click.option(
    "-uf",
    "--users-first",
    "--user-first",
    "users_first",
    help="Process all users first rather than one at a time (affects --action)",
    default=False,
    is_flag=True,  # Shorthand for action="store_true"
)

individual_search_option = click.option(
    "-fi",
    "--individual",
    help="Search each username as a separate request when --username is provided",
    default=False,
    is_flag=True,
)

search_entire_list_option = click.option(
    "-fl",
    "--list",
    help="Search entire enabled lists before filtering for usernames when --username is provided",
    default=False,
    is_flag=True,
)

# Create the option group with mutually exclusive constraints

advanced_processing_options = click.option_group(
    "Advanced Search & Processing Options",
    users_first_option,
    click.constraints.mutually_exclusive(
        individual_search_option, search_entire_list_option
    ),
    help="Choose how usernames are searched, and define the order in which users are processed for actions",
)
