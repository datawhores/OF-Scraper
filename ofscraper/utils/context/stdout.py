import contextlib
import os
import sys

import ofscraper.utils.args.accessors.read as read_args
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


@contextlib.contextmanager
def nostdout():
    try:
        save_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        yield
        sys.stdout = save_stdout
    except:
        None
        yield
        None
