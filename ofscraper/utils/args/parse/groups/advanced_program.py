import cloup as click

from ofscraper.utils.args.parse.arguments.advanced_program import (
    download_script_option,
    dynamic_rules_option,
    key_mode_option,
    no_api_cache_option,
    no_cache_option,
    update_profile_option,
)

# Create the option grou
advanced_options = click.option_group(
    "Advanced Program Options",
    no_cache_option,
    no_api_cache_option,
    key_mode_option,
    dynamic_rules_option,
    update_profile_option,
    download_script_option,
    help="Advanced control of program behavior",
)
