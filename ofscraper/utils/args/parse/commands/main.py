import cloup as click

from ofscraper.utils.args.parse.group_bundles.advanced_common import advanced_args
from ofscraper.utils.args.parse.group_bundles.main import main_program_args
import ofscraper.utils.args.parse.arguments.utils.retry as retry_helper


@click.group(
    help="OF-Scraper Options",
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True,
    show_constraints=True,
)
@main_program_args
@advanced_args
@click.pass_context
def program(ctx, *args, **kwargs):
    ctx = retry_helper.retry_modifiy(ctx)
    return ctx.params, ctx.info_name
