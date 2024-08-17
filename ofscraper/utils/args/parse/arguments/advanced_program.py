import cloup as click

from ofscraper.const.constants import DYNAMIC_OPTIONS, KEY_OPTIONS

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
    help="Key mode for decrypting content",
    default=None,
    type=click.Choice(KEY_OPTIONS),
)


key_db_option = click.option(
    "-kd",
    "--keydb-api",
    "--key-db-api",
    "keydb_api",
    help="api key for keydb cdrm",
    default=None,
)

private_key_option = click.option(
    "-pk",
    "--private-key",
    "private_key",
    help="private key path for manual cdrm",
    default=None,
)

client_id_option = click.option(
    "-ci",
    "--client-id",
    "client_id",
    help="client id path for manual cdrm",
    default=None,
)

auth_fail = click.option(
    "-al",
    "--auth-fail",
    "--auth-quit",
    "auth_fail",
    help="quit on authentication failure, rather then prompting",
    default=False,
    is_flag=True,
)
dynamic_rules_option = click.option(
    "-dr",
    "--dynamic-rules",
    "--dynamic-rule",
    help="Dynamic signing",
    default=None,
    type=click.Choice(DYNAMIC_OPTIONS, case_sensitive=False),
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
    runs a script post model download script
    addional args sent to script username, model_id, media json ,and post json
    """,
)


post_script_option = click.option(
    "-ps",
    "--post-script",
    "post_script",
    help="""
    \b
    runs a script after processing all users
    addional args sent to script userdata array,
    """,
)
