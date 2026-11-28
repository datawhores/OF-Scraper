from click import UsageError

from ofscraper.utils.args.parse.group_bundles.live_tui import live_tui_args


@live_tui_args
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
