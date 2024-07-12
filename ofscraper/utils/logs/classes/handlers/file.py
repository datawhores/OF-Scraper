import logging
import asyncio
from filelock import FileLock
from ofscraper.utils.system.system import getName
import ofscraper.utils.paths.common as common_paths

class StreamHandlerMulti(logging.StreamHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args, **kwargs)
        self.last_process=None
        self.lock=FileLock(common_paths.getRich())
        self.loop = asyncio.new_event_loop()
    def emit(self, record):
        self.loop.create_task(self._async_emit(record))

    async def _async_emit(self, record):
        try:
            super().emit(record)
        except Exception as e:
            print(e)
    def close(self):
        # with self.lock:
        self.loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(self.loop)))
        self.loop.close()

        

