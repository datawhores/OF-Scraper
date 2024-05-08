import cloup as click

from ofscraper.const.constants import KEY_OPTIONS

no_cache_option = click.option(
    "-nc",
    "--no-cache",
    help="Disable cache and forces consecutive api scan",
    default=False,
    is_flag=True,
)  # Define individual options


no_api_cache_option = click.option(
    "-nca",
    "--no-api-cache",
    help="Forces consecutive api scan",
    default=False,
    is_flag=True,
)

key_mode_option = click.option(
    "-k",
    "--key-mode",
    help="Key mode override",
    default=None,
    type=click.Choice(KEY_OPTIONS),
)

dynamic_rules_option = click.option(
    "-dr",
    "--dynamic-rules",
    help="Dynamic signing",
    default=None,
    type=click.Choice(["dc", "deviint", "sneaky"], case_sensitive=False),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

update_profile_option = click.option(
    "-up",
    "--update-profile",
    help="Get up-to-date profile info instead of using cache",
    default=False,
    is_flag=True,
)

download_script_option = click.option(
    "-ds",
    "--download-script",
    "download_script",
    help="""
    \b
    runs a script post model download
    addional args sent to script username, model_id, media json ,and post json
    """,
)

# Create the option group
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
