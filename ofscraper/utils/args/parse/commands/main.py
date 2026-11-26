import cloup as click
from click import UsageError

import ofscraper.commands.tools as tools
from ofscraper.utils.args.parse.group_bundles.advanced_common import main_advanced_args
from ofscraper.utils.args.parse.group_bundles.main import main_program_args
import ofscraper.utils.args.parse.arguments.utils.retry as retry_helper


@click.group(
    help="OF-Scraper Options",
    epilog=tools.help_section(),
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True,
    show_constraints=True,
)
@main_program_args
@main_advanced_args
@click.pass_context
def program(ctx, *args, **kwargs):
    # a subcommand's own options replace these, so the migration would be
    # dropped without a word
    if ctx.invoked_subcommand and kwargs.get("migrate_sqlite_to_postgres"):
        raise UsageError(
            f"--migrate-sqlite-to-postgres can't be used with '{ctx.invoked_subcommand}'. "
            "Run it on its own: ofscraper --migrate-sqlite-to-postgres PATH"
        )
    ctx = retry_helper.retry_modifiy(ctx)
    return ctx.params, ctx.info_name
