import itertools

import cloup as click

import ofscraper.utils.args.groups.common_args as common
import ofscraper.utils.args.helpers as helpers


@click.command("paid_check", help="Produces a table of purchases from a model")
@click.constraints.require_one(
    click.option(
        "-u",
        "--username",
        help="Scan purchases via username(s)",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
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
    return ctx.params, ctx.invoked_subcommand
