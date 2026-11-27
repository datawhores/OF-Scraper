import re

import cloup as click

from ofscraper.utils.args.callbacks.parse.string import (
    StringSplitParse,
)
from ofscraper.utils.args.types.choice import MutuallyExclusiveMultichoice


def _parse_profiles(ctx, param, value):
    out = []
    seen = set()
    for raw in value or ():
        for part in re.split(r"[,\s]+", str(raw)):
            name = part.strip()
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    return out

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

profiles_option = click.option(
    "--profiles",
    help="Comma- or space-separated profiles to run one after another on each --daemon pass (each in its own child process; cannot be combined with --live-watch or --profile)",
    multiple=True,
    default=[],
    callback=_parse_profiles,
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

dry_run_option = click.option(
    "--dry-run",
    "dry_run",
    help="Scan as usual and report how many files a download would attempt, without downloading or changing anything; needs --action download",
    is_flag=True,
    default=False,
)

dry_run_json_option = click.option(
    "--dry-run-json",
    "dry_run_json",
    help="Also write the dry run's report to this file as JSON; implies --dry-run",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
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

live_jitter_option = click.option(
    "--live-jitter",
    help="Max random extra seconds added to each --live-watch check interval (default 10)",
    type=click.FloatRange(min=0),
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
