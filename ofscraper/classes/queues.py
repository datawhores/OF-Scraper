import platform
import asyncio
import multiprocessing
import aioprocessing
class Queues():
    def __init__(self) -> None:
        if platform.system()=="Windows":
            self.queue=multiprocessing.Queue()
        else:
            self.queue=aioprocessing.AioQueue()

 

    def coro_get(self):
        if isinstance(self.queue,aioprocessing.queues.AioQueue):
            async def inner():
                return await self.queue.coro_get()        
            return asyncio.create_task(inner())
        else:
            return self.queue.get()
    def get(self):
        return self.queue.get()
    def get_nowait(self):
        return self.queue.get_nowait()
    def put(self,ele):
        self.queue.put(ele)
    def coro_put(self,ele):
        if isinstance(self.queue,aioprocessing.queues.AioQueue):
            async def inner(ele):
                await self.queue.coro_put(ele)        
            asyncio.create_task(inner(ele))
        else:
            self.queue.put(ele)
    def put_nowait(self,ele):
        self.queue.put_nowait(ele)
  
     

  