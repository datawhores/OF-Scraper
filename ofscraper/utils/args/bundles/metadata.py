import cloup as click
from click.utils import echo

from ofscraper.const.constants import METADATA_OPTIONS
from ofscraper.utils.args.bundles.main import main_program_args

from ofscraper.utils.args.bundles.common import common_args
from ofscraper.utils.args.bundles.advanced_common import advanced_args
def metadata_args(func):
    @click.command(
    "metadata",
    short_help="""\b
               Modify metadata or db files""",
    help="""
Uses API to modify db files without the need for downloading
""",
    )
    
    @click.option_group( 
        "metadata_options",
        click.option(
        "-md",
        "--metadata",
        "metadata",
        help="""
        \b
        How should metadata be handled
        update: update download status based on file presence, and update metadata fields via api
        check: only update metadata fields via api
        complete: update download to true, and update metadata fields
        """,
        type=click.Choice(METADATA_OPTIONS)
    ))
    @common_args
    @main_program_args
    @advanced_args
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        ctx.params.pop("key_mode")
        return func(ctx, *args, **kwargs)
    return wrapper