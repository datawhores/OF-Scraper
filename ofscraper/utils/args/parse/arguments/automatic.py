import cloup as click

from ofscraper.utils.args.callbacks.string import (
    StringSplitParse,
)
from ofscraper.utils.args.types.choice import MutuallyExclusiveMultichoice

daemon_option = click.option(
    "-d",
    "--daemon",
    help="Run script in the background. Set value to minimum minutes between script runs. Overdue runs will run as soon as previous run finishes",
    type=float,
)

action_option = click.option(
    "-a",
    "--action",
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
