import logging
from filelock import FileLock
import asyncio
import ofscraper.utils.paths.common as common_paths

class StreamHandlerMulti(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        self.last_process = None
        self.lock = FileLock(common_paths.getRich())  # Cross-process lock
        self.loop = asyncio.new_event_loop()  # For async operations (if needed)

    def set_stream(self, new_stream):
        """Safely replace the current output stream."""
        with self.lock:
            # Flush and replace stream
            if self.stream:
                try:
                    self.stream.flush()
                except Exception:
                    pass
            self.stream = new_stream

    def emit(self, record):
        """Thread/process-safe log emission."""
        with self.lock:
            try:
                super().emit(record)
            except Exception:
                self.handleError(record)

    def flush(self):
        """Ensure flush operations are locked."""
        with self.lock:
            if self.stream:
                try:
                    self.stream.flush()
                except Exception:
                    pass

    def close(self):
        """Cleanup resources on handler shutdown."""
        with self.lock:
            super().close()
            if self.loop.is_running():
                self.loop.stop()
            self.loop.close()