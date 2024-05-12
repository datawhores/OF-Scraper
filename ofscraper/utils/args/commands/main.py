import cloup as click
import arrow

from ofscraper.utils.args.bundles.advanced_common import advanced_args
from ofscraper.utils.args.bundles.common import common_args
from ofscraper.utils.args.bundles.main import main_program_args


@click.group(
    help="OF-Scraper Options",
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True,
)
@common_args
@main_program_args
@advanced_args
@click.pass_context
def program(ctx, *args, **kwargs):
    #fix dates
    params=ctx.params
    if params["after"]:
        params["after"]=arrow.get(params["after"])
    params["before_original"]=params["before"]
    params["before"]=arrow.get(params["before"] or arrow.now()).shift(days=4)
    return ctx.params, ctx.info_name
