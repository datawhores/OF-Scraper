from aiolimiter import AsyncLimiter
import ofscraper.utils.settings as settings

CHUNK_SIZE = 10 * 1024 * 1024


class LeakyBucket(AsyncLimiter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def acquire(self, amount: float = 1):
        if settings.get_settings().download_limit <= 0:
            return
        amount = amount or CHUNK_SIZE
        # AsyncLimiter refuses more than one period's worth at once, and a
        # chunk can be bigger than the limit (metadata reads 30 MB chunks)
        while amount > self.max_rate:
            await super().acquire(self.max_rate)
            amount -= self.max_rate
        await super().acquire(amount)
