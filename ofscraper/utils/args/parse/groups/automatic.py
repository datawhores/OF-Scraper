import cloup as click
from ofscraper.utils.args.parse.arguments.automatic import daemon_option,action_option
# Create the option group
automatic_options = click.option_group(
    "Automation Options",
    daemon_option,
    action_option,
    help="Control automated actions (like/unlike/download) and background execution",
)