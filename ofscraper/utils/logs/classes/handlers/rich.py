

import logging
from collections import deque 
import time
from rich.logging import RichHandler
from rich.traceback import Traceback
from rich.console import Group
from ofscraper.utils.console import get_console

logs=deque()

def flush_buffer(event=None):
    """Flushes the buffer to the console."""
    i=0
    sleep=.5
    close=False
    while True:
        log_rends=[]
        records=[]
        try:
            num=min(len(logs),100)
            if num>0:
                for _ in range(num):
                    log_renderable,record=logs.pop()
                    if record.message=="None":
                        close=True
                        continue
                    log_rends.append(log_renderable)
                    records.append(record)
                    
                    # if isinstance(self.console.file, NullFile):
                    #         i=k
                    #         # Handles pythonw, where stdout/stderr are null, and we return NullFile
                    #         # instance from Console.file. In this case, we still want to make a log record
                    #         # even though we won't be w
                    #         # riting anything to a file.
                    #         for ele in  map(lambda x:x[1],logs[i:k]):
                    #             RichHandler().handleError(ele)          
                try:
                    get_console().print(Group(*log_rends))
                except Exception as E:
                    print(E)
            if close:
                break

        except:
            continue
        finally:
            if event and event.is_set():
                return
            time.sleep(sleep)


class RichHandlerMulti(RichHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_process = None
        self._buffer_size = {
            logging.getLevelName("TRACE"):4,
            logging.DEBUG: 2,  # Adjust buffer sizes based on log level
            logging.INFO: 3,
            logging.WARNING: 1,
            logging.ERROR: 1,
            logging.CRITICAL: 1,
        }
        self._sleep=.3

    @property
    def buffer_size(self):
        return self._buffer_size
    @buffer_size.setter
    def buffer_size(self, value):
        self._buffer_size=(self._buffer_size or {})
        self._buffer_size.update(value)


    def emit(self, record,*args, **kwargs):
        message=self.format(record)
        traceback = None
        if (
        self.rich_tracebacks
        and record.exc_info
        and record.exc_info != (None, None, None)
        ):
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type is not None
            assert exc_value is not None
            traceback = Traceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                width=self.tracebacks_width,
                extra_lines=self.tracebacks_extra_lines,
                theme=self.tracebacks_theme,
                word_wrap=self.tracebacks_word_wrap,
                show_locals=self.tracebacks_show_locals,
                locals_max_length=self.locals_max_length,
                locals_max_string=self.locals_max_string,
                suppress=self.tracebacks_suppress,
            )
            message = record.getMessage()
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(record, formatter.datefmt)
                message = formatter.formatMessage(record)
        message_renderable = self.render_message(record,message)
        log_renderable = self.render(
            record=record, traceback=traceback, message_renderable=message_renderable
        )
        logs.append((log_renderable,record))




        

        

