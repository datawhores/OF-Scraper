import cloup as click

from ofscraper.utils.args.parse.arguments.advanced_program import (
    download_script_option,
    post_script_option,
    dynamic_rules_option,
    key_mode_option,
    key_db_option,
    private_key_option,
    client_id_option,
    no_api_cache_option,
    no_cache_option,
    update_profile_option,
    auth_fail,
)

advanced_options_desc = "Advanced Program Options"
advanced_options_help = "Advanced control of program behavior"
advanced_options_tuple = (
    no_cache_option,
    no_api_cache_option,
    key_mode_option,
    key_db_option,
    private_key_option,
    client_id_option,
    dynamic_rules_option,
    update_profile_option,
    auth_fail,
    download_script_option,
    post_script_option,
)
# Create the option group
advanced_options = click.option_group(
    advanced_options_desc, *advanced_options_tuple, help=advanced_options_help
)
