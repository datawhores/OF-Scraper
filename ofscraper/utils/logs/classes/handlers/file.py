import logging
from filelock import FileLock
from ofscraper.utils.system.system import getName
import ofscraper.utils.paths.common as common_paths

class StreamHandlerMulti(logging.StreamHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args, **kwargs)
        self.last_process=None
        self.lock=FileLock(common_paths.getRich())
    def emit(self, *args, **kwargs):
        super().emit(*args, **kwargs)
        

        

