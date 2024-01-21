import contextlib
import io
import os
import sys

import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants


@contextlib.contextmanager
def lowstdout():
    if read_args.retriveArgs().output in constants.getattr("SUPRESS_OUTPUTS"):
        save_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        yield
        sys.stdout = save_stdout
    else:
        None
        yield
        None


# @contextlib.contextmanager
# def lowstdout():
#     if logging.getLogger("ofscraper").handlers[1].level>constants.getattr("SUPPRESS_LOG_LEVEL"):
#         save_stdout = sys.stdout
#         sys.stdout = open(os.devnull, 'w')
#         yield
#         sys.stdout = save_stdout
#     else:
#         None
#         yield
#         None


@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = io.BytesIO()
    yield
    sys.stdout = save_stdout
