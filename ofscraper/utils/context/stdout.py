import contextlib
import os
import sys

import ofscraper.utils.of_env.of_env as of_env

import ofscraper.utils.settings as settings


@contextlib.contextmanager
def lowstdout():
    if settings.get_settings().output_level in of_env.getattr("SUPRESS_OUTPUTS"):
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
