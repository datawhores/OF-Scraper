import re

from ofscraper.utils.args.callbacks.string import StringSplitParse


def FileCallback(ctx, param, values):
    nested_array = list(map(lambda value: value.readlines(), values))
    for i in range(len(nested_array)):
        inner = nested_array[i]
        for k in range(len(inner)):
            inner[k] = re.sub(r"\n", "", inner[k])
    return StringSplitParse(ctx, param, nested_array)
