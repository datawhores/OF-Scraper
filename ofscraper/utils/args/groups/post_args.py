import itertools

import cloup as click

import ofscraper.utils.args.groups.common_args as common
import ofscraper.utils.args.helpers as helpers


@click.command("post_check",  short_help="""\b
               Produces a media table from posts with filterable entries and quick downloads""",
               help="""The post_check subcommand gathers information on media content from posts
It presents this data in a table format with filtering options for focused searches 
Allows unlocked media entries to be directly downloaded through the table""")
@click.constraints.require_one(
    click.option(
        "-u",
        "--url",
        help="Scan posts via space or comma seperated list of urls",
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
        help="Scan posts via a file with line-separated URL(s)",
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
    help="Force retrieval of new posts info from API",
    is_flag=True,
    default=False,
)
@click.option(
    "-ca",
    "--check-area",
    help="Select areas to check (multiple allowed, separated by spaces)",
    default=["Timeline", "Pinned", "Archived"],
    type=click.Choice(
        ["Timeline", "Pinned", "Archived", "Labels"], case_sensitive=False
    ),
    callback=lambda ctx, param, value: (
        list(set(helpers.post_check_area(value))) if value else None
    ),
    multiple=True,
)
@common.common_params
@common.common_other_params
@click.pass_context
def post_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
