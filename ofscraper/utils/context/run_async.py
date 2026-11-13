import asyncio
import ofscraper.utils.system.system as system


def run(coro):
    def inner(*args, **kwargs):
        try:
            # Get the loop or create a new one
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = system.new_event_loop()
            asyncio.set_event_loop(loop)
        if not loop.is_running():
            # Use run_until_complete for the top-level coro
            return loop.run_until_complete(coro(*args, **kwargs))
        # If the loop is ALREADY running (nested call), just return the coro
        return coro(*args, **kwargs)

    return inner
