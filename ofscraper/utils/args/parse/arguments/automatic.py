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

daemon_jitter_option = click.option(
    "--daemon-jitter",
    help="Add a random delay up to this many minutes to each --daemon interval (default 0)",
    type=click.FloatRange(min=0),
    default=0.0,
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

# Livestream recording (Fansly, and OnlyFans with the optional "live" extra).
live_option = click.option(
    "--live",
    help="Record the selected creators (all followed creators without -u) who are live now, then continue. OnlyFans needs the optional live install (a Chromium browser)",
    is_flag=True,
    default=False,
)

live_watch_option = click.option(
    "--live-watch",
    help="Keep checking who is live and record them; with --daemon it runs beside the scheduled scrapes. With -u or user filters, the creators to watch are chosen once, when watching starts",
    is_flag=True,
    default=False,
)

live_interval_option = click.option(
    "--live-interval",
    help="Seconds between live checks in --live-watch (default 60, plus up to 10 s of jitter)",
    type=click.IntRange(min=10),
    default=None,
)

live_max_option = click.option(
    "--live-max",
    help="Most livestreams recorded at the same time (default 2)",
    type=click.IntRange(min=1),
    default=None,
)

live_chat_option = click.option(
    "--live-chat",
    help="Fansly only: also save livestream chat to a .jsonl file (read-only; off by default)",
    is_flag=True,
    default=False,
)
