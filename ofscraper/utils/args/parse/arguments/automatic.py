import cloup as click

from ofscraper.utils.args.callbacks.parse.string import (
    StringSplitParse,
)
from ofscraper.utils.args.types.choice import MutuallyExclusiveMultichoice

daemon_option = click.option(
    "-d",
    "--daemon",
    help="Run script in the background. Set value for how many minutes between script runs",
    type=float,
)

action_option = click.option(
    "-a",
    "--action",
    "--actions",
    "actions",
    help="""
    Select batch action(s) to perform [like,unlike,download].
    Accepts space or comma-separated list. Like and unlike cannot be combined.
    """,
    multiple=True,
    type=MutuallyExclusiveMultichoice(
        ["unlike", "like", "download"],
        exclusion=["like", "unlike"],
        case_sensitive=False,
    ),
    default=[],
    callback=StringSplitParse,
)
