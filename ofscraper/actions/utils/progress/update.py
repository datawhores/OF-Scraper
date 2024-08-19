import ofscraper.actions.utils.globals as common_globals


async def update_total(update):
    async with common_globals.lock:
        common_globals.total_bytes += update
