import asyncio


class semaphoreDelayed(asyncio.Semaphore):
    def __init__(self, delay=-1, sem=None) -> None:
        self._delay = delay or 0
        super().__init__(sem or 10000000)

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, value):
        self._delay = value

    async def acquire(self):
        await super().acquire()
        if self._delay:
            await asyncio.sleep(self._delay)
