from filelock import FileLock
from rich.logging import RichHandler
from rich._null_file import NullFile
from rich.traceback import Traceback
from rich.console import Group
import ofscraper.utils.paths.common as common_paths





class RichHandlerMulti( RichHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args, **kwargs)
        self.last_process=None
        self.lock=FileLock(common_paths.getRich())
    def emit(self, *args, **kwargs):
        """Invoked by logging."""
        full_message=[]
        if len(args)==0:
            return
        for record in args:
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
            full_message.append(log_renderable)
        if isinstance(self.console.file, NullFile):
            # Handles pythonw, where stdout/stderr are null, and we return NullFile
            # instance from Console.file. In this case, we still want to make a log record
            # even though we won't be writing anything to a file.
            self.handleError(record)
        else:
            try:
                self.console.print(Group(*full_message))
            except Exception:
                self.handleError(record)
        

        

