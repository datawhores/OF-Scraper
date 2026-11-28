import functools

import cloup as click
from click.exceptions import UsageError

from ofscraper.utils.args.parse.group_bundles.common import common_args
from ofscraper.utils.args.parse.groups.advanced_processing import (
    advanced_processing_options,
)
from ofscraper.utils.args.parse.groups.advanced_user_filter import (
    advanced_userfilters_options,
)
from ofscraper.utils.args.parse.groups.automatic import automatic_options
from ofscraper.utils.args.parse.groups.post_filter import post_filter_options
from ofscraper.utils.args.parse.groups.user_list import userlist_options
from ofscraper.utils.args.parse.groups.user_select import user_select_options
from ofscraper.utils.args.parse.groups.user_sort import user_sorting_options

# import click


def check_dry_run(params, subcommand=None):
    """--dry-run goes with one download run, nothing else that changes things."""
    if params.get("dry_run_json"):
        params["dry_run"] = True
    if not params.get("dry_run"):
        return
    if subcommand:
        # a subcommand runs instead of the scraper and doesn't see --dry-run,
        # so it would change things for real
        raise UsageError(f"--dry-run can't be used with {subcommand}")
    if params.get("daemon"):
        raise UsageError("--dry-run can't be used with --daemon")
    if params.get("live") or params.get("live_watch"):
        raise UsageError("--dry-run can't be used with --live or --live-watch")
    if "download" not in (params.get("actions") or []) and not params.get("scrape_paid"):
        raise UsageError(
            "--dry-run needs --action download; like and unlike aren't run in a dry run"
        )


def main_program_args(func):
    @common_args
    @post_filter_options
    @automatic_options
    @user_select_options
    @userlist_options
    @advanced_userfilters_options
    @user_sorting_options
    @advanced_processing_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        check_dry_run(ctx.params, ctx.invoked_subcommand)
        return func(ctx, *args, **kwargs)

    return wrapper
