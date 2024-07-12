from filelock import FileLock
from rich.logging import RichHandler
from ofscraper.utils.system.system import getName
import ofscraper.utils.paths.common as common_paths

class richHandlerMulti( RichHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args, **kwargs)
        self.last_process=None
        self.lock=FileLock(common_paths.getRich())
    def emit(self, *args, **kwargs):
        with self.lock:
            super().emit(*args, **kwargs)
            self.last_process=getName()
        

        

