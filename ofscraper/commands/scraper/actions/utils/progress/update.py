import ofscraper.commands.scraper.actions.utils.globals as common_globals


async def update_total(update, ctx=None):
    """Add update to the run's total_bytes. ctx is the DownloadContext, by
    default the current one."""
    if ctx is None:
        ctx = common_globals.current()
    async with ctx.lock:
        ctx.total_bytes += update
