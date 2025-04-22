from aiolimiter import AsyncLimiter
import ofscraper.utils.settings as settings

CHUNK_SIZE = 10 * 1024 * 1024


class LeakyBucket(AsyncLimiter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def acquire(self, amount: float = 1):
        if settings.get_settings().download_limit <= 0:
            return
        await super().acquire(amount or CHUNK_SIZE)
