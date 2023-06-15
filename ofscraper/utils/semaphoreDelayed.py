import asyncio

class semaphoreDelayed(asyncio.Semaphore):
    def __init__(self, value: int = 1) -> None:
        self._delay=0
        super().__init__(value)
    @property
    def delay(self):
        return self._delay
    @delay.setter
    def delay(self, value):
        self._delay = value
    async def acquire(self):
        await super().acquire()
        await asyncio.sleep(self._delay)
