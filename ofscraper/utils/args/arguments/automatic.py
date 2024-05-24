import itertools

import cloup as click

import ofscraper.utils.args.helpers.type as type

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
    type=type.action_helper,  # Assuming helpers.action_helper is defined elsewhere
    default=None,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
)

# Create the option group

automatic_options = click.option_group(
    "Automation Options",
    daemon_option,
    action_option,
    help="Control automated actions (like/unlike/download) and background execution",
)
