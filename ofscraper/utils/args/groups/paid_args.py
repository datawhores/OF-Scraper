import itertools

import cloup as click

import ofscraper.utils.args.groups.common_args as common
import ofscraper.utils.args.helpers as helpers


@click.command("paid_check", short_help="""\b
               Produces a media table from purchases with filterable entries and quick downloads""",help=
               """
The paid_check subcommand gathers information on media content from purchases
It presents this data in a table format with filtering options for focused searches 
Allows unlocked media entries to be directly downloaded through the table
""")
@click.constraints.require_one(
    click.option(
        "-u",
        "--usernames",
        "--username",
        "usernames",
        help="Scan purchases via username(s)",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else []
        ),
    ),
    click.option(
        "-f",
        "--file",
        help="Scan pu via a file with line-separated URL(s)",
        default=None,
        type=helpers.check_filehelper,
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
@common.common_params
@common.common_other_params
@click.pass_context
def paid_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
