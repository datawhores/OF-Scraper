import cloup as click

from ofscraper.utils.const import KEY_OPTIONS, DYNAMIC_OPTIONS, DYNAMIC_ALIASES

no_cache_option = click.option(
    "-nc",
    "--no-cache",
    help="Disable cache and force a fresh sequential API scan",
    default=False,
    is_flag=True,
)  # Define individual options


no_api_cache_option = click.option(
    "-nca",
    "--no-api-cache",
    help="Force a fresh sequential API scan",
    default=False,
    is_flag=True,
)

key_mode_option = click.option(
    "-k",
    "--key-mode",
    help="Key mode for decrypting content (cdrm is deprecated: its service no longer works)",
    default=None,
    type=click.Choice(KEY_OPTIONS),
)


private_key_option = click.option(
    "-pk",
    "--private-key",
    "private_key",
    help="Private key path for manual key mode",
    default=None,
)

client_id_option = click.option(
    "-ci",
    "--client-id",
    "client_id",
    help="Client ID path for manual key mode",
    default=None,
)

migrate_sqlite_to_postgres_option = click.option(
    "--migrate-sqlite-to-postgres",
    "migrate_sqlite_to_postgres",
    help="Copy a user_data.db file (such as the one Merge Databases writes), or a folder of them, into the PostgreSQL database OFSC_DATABASE_URL names, then exit",
    default=None,
    type=click.Path(exists=True),
)

auth_fail = click.option(
    "-al",
    "--auth-fail",
    "--auth-quit",
    "auth_fail",
    help="Quit on authentication failure rather than prompting",
    default=False,
    is_flag=True,
)
dynamic_rules_option = click.option(
    "-dr",
    "--dynamic-rules",
    "--dynamic-rule",
    help="Dynamic signing rule source",
    default=None,
    # the same names config.json accepts, short names included (#232)
    type=click.Choice([*DYNAMIC_OPTIONS, *DYNAMIC_ALIASES], case_sensitive=False),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

update_profile_option = click.option(
    "-up",
    "--update-profile",
    help="Get up-to-date profile info instead of using cache",
    default=False,
    is_flag=True,
)
