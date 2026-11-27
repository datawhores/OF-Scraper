import cloup as click
from click import UsageError

from ofscraper.utils.args.parse.arguments.automatic import (
    live_chat_option,
    live_interval_option,
    live_max_option,
)
from ofscraper.utils.args.parse.groups.advanced_processing import (
    advanced_processing_options,
)
from ofscraper.utils.args.parse.groups.advanced_program import advanced_options
from ofscraper.utils.args.parse.groups.advanced_user_filter import (
    advanced_userfilters_options,
)
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.program import program_options
from ofscraper.utils.args.parse.groups.user_list import userlist_options
from ofscraper.utils.args.parse.groups.user_select import user_select_options
from ofscraper.utils.args.parse.groups.user_sort import user_sorting_options

live_once_option = click.option(
    "--once",
    "--live",
    "live",
    help="Check who is live right now, record active streams until they end, and exit without polling again",
    is_flag=True,
    default=False,
)


@click.command(
    "live_tui",
    short_help="Interactive TUI dashboard for monitoring and recording livestreams",
    help=(
        "Open an interactive terminal dashboard (TUI) to monitor and record "
        "Fansly or OnlyFans livestreams in real time. Polls continuously by "
        "default; pass --once / --live for a single check."
    ),
    show_constraints=True,
)
@program_options
@logging_options
@click.option_group(
    "Livestream Options",
    live_once_option,
    live_interval_option,
    live_max_option,
    live_chat_option,
    help="Control livestream polling, concurrency, and Fansly live chat capture",
)
@user_select_options
@userlist_options
@advanced_userfilters_options
@user_sorting_options
@advanced_processing_options
@advanced_options
@click.pass_context
def live_tui(ctx, *args, **kwargs):
    if ctx.parent:
        for key in ("config", "profile", "site", "env_files"):
            if not ctx.params.get(key) and ctx.parent.params.get(key):
                ctx.params[key] = ctx.parent.params[key]
    if ctx.params.get("no_rich") or (ctx.parent and ctx.parent.params.get("no_rich")):
        raise UsageError("live_tui cannot be used with --no-live / --no-rich", ctx=ctx)
    ctx.params["live_tui"] = True
    ctx.params["live_watch"] = not bool(ctx.params.get("live"))
    ctx.params["actions"] = []
    return ctx.params, (ctx.parent.info_name if ctx.parent else "OF-Scraper")
