
# checkmode  args
import cloup as click
from ofscraper.utils.args.types.arrow import ArrowType

preview_option = click.option(
    "-p/-np",
    "--preview/--no-preview",
    "preview",
    help="""
        \b
        Flag for filtering accounts based on preview status.
        [select one --preview or --no-preview]""",
    default=None,
    required=False,
    is_flag=True,
)

posted_after=click.option(
            "-pf",
            "--posted-after",
            help="Process posts posted or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
            type=ArrowType(),
        )
posted_before=click.option(
            "-pb",
            "--posted-before",
            help="Process posts posted at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
            type=ArrowType(),
)