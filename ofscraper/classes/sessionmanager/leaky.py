import asyncio
from aiolimiter import AsyncLimiter
import ofscraper.utils.settings as settings
from aiolimiter.compat import wait_for


class LeakyBucket(AsyncLimiter):
    def __init__(self, *args, **kwargs):
        self.max_amount = 1024 * 1024 * 10
        super().__init__(*args, **kwargs)

    async def acquire(self, amount: float = 1):
        if settings.get_download_limit() <= 0:
            return
        if not isinstance(amount, int):
            amount = len(amount)
        loop = asyncio.get_running_loop()
        task = asyncio.current_task(loop)
        assert task is not None
        while not self.has_capacity(amount):
            # wait for the next drip to have left the bucket
            # add a future to the _waiters map to be notified
            # 'early' if capacity has come up
            fut = loop.create_future()
            self._waiters[task] = fut
            try:
                await wait_for(
                    asyncio.shield(fut), 1 / self._rate_per_sec * amount, loop=loop
                )
            except asyncio.TimeoutError:
                pass
            fut.cancel()
        self._waiters.pop(task, None)
        self._level += amount
        return None

    def has_capacity(self, amount: float = 1) -> bool:
        """Check if there is enough capacity remaining in the limiter

        :param amount: How much capacity you need to be available.

        """
        self._leak()
        requested = self._level + amount
        # if there are tasks waiting for capacity, signal to the first
        # there there may be some now (they won't wake up until this task
        # yields with an await)
        if requested < self.max_rate:
            for fut in self._waiters.values():
                if not fut.done():
                    fut.set_result(True)
                    break
        # allows for one packet to be received until bucket empties
        if self._level > self.max_rate:
            return False
        return self._level + amount <= self.max_amount
