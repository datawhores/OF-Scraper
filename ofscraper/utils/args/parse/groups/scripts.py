import cloup as click

from ofscraper.utils.args.parse.arguments.scripts import (
    after_action_script_option,
    naming_script_option,
    post_script_option,
    after_download_option,
    skip_download_script,
)

script_options_desc = "Program Scripts"
script_options_help = "Custom Scripts that run at different points of the run"
script_options_tuple = (
    after_action_script_option,
    naming_script_option,
    post_script_option,
    after_download_option,
    skip_download_script,
)
# Create the option group
script_options = click.option_group(
    script_options_desc, *script_options_tuple, help=script_options_help
)
