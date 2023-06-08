import contextlib
import io
import os
import sys
import ofscraper.constants as constants
import logging

@contextlib.contextmanager
def lowstdout():
    if logging.getLogger("ofscraper").handlers[1].level>constants.SUPPRESS_LOG_LEVEL:
        save_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        yield
        sys.stdout = save_stdout
    else:
        None
        yield
        None

@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = io.BytesIO()
    yield
    sys.stdout = save_stdout
    