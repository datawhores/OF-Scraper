import logging
import asyncio
from filelock import FileLock
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.logs.globals as log_globals


class StreamHandlerMulti(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_process = None
        self.lock = FileLock(common_paths.getRich())
        self.loop = asyncio.new_event_loop()

    def emit(self, record):
        if hasattr(record, "message") and (record.message in log_globals.stop_codes):
            return
        super().emit(record)
