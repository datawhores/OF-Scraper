import itertools

import cloup as click

import ofscraper.utils.args.helpers.type as type
from ofscraper.utils.args.bundles.advanced_common import advanced_args
from ofscraper.utils.args.bundles.common import common_args
from ofscraper.utils.args.helpers.check import check_mode_changes


def paid_check_args(func):
    @click.command(
        "paid_check",
        short_help="""\b
                Produces a media table from purchases with filterable entries and quick downloads""",
        help="""
    The paid_check subcommand gathers information on media content from purchases
    It presents this data in a table format with filtering options for focused searches 
    Allows unlocked media entries to be directly downloaded through the table
    """,
    )
    @common_args
    @click.constraints.require_one(
        click.option(
            "-u",
            "--usernames",
            "--username",
            "check_usernames",
            help="Scan purchases via username(s)",
            default=None,
            multiple=True,
            type=type.check_strhelper,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
        ),
        click.option(
            "-f",
            "--file",
            help="Scan pu via a file with line-separated URL(s)",
            default=None,
            type=type.check_filehelper,
            multiple=True,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
        ),
    )
    @click.option(
        "-fo",
        "--force",
        help="Force retrieval of new purchases info from API",
        is_flag=True,
        default=False,
    )
    @advanced_args
    @check_mode_changes
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
