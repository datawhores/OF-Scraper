import contextlib
import os
import sys

import ofscraper.utils.of_env.of_env as of_env

import ofscraper.utils.settings as settings


@contextlib.contextmanager
def lowstdout():
    if settings.get_settings().output_level in of_env.getattr("SUPRESS_OUTPUTS"):
        with nostdout():
            yield
    else:
        yield


@contextlib.contextmanager
def nostdout():
    # always put stdout back, also when the body raises (e.g. ctrl+c in a
    # prompt); yielding a second time from an except block turned that into
    # "generator didn't stop after throw()" and left stdout at devnull
    save_stdout = sys.stdout
    with open(os.devnull, "w") as devnull:
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = save_stdout
