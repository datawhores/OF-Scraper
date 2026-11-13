import re

from ofscraper.utils.args.callbacks.parse.string import StringSplitParse


def read_lines_and_close(value):
    # values are lazy click.File objects: close each one once it's read, so a
    # usage error later in parsing can't leave it open (#220). stdin ("-") is
    # left open, as close_intelligently only closes files click opened.
    try:
        return value.readlines()
    finally:
        value.close_intelligently()


def FileCallback(ctx, param, values):
    nested_array = list(map(read_lines_and_close, values))
    for i in range(len(nested_array)):
        inner = nested_array[i]
        for k in range(len(inner)):
            inner[k] = re.sub(r"\n", "", inner[k])
    return StringSplitParse(ctx, param, nested_array)
