import re

from ofscraper.utils.args.callbacks.choice import MultiChoiceCallback


def StringSplitParse(ctx, param, value):
    out = []
    for val in value:
        if isinstance(val, str):
            val = re.split(",| ", val)
        out.append(val)
    return MultiChoiceCallback(ctx, param, out)


def StringSplitNormalizeParse(ctx, param, value):
    out = []
    for val in value:
        if isinstance(val, str):
            val = re.split(",| ", val)
        val = list(map(lambda x: re.sub(r"[^a-zA-Z-\*\+]", "", str.title(x)), val))
        out.append(val)
    out = MultiChoiceCallback(ctx, param, out)
    return out


def StringSplitParseTitle(ctx, param, value):
    out = StringSplitParse(ctx, param, value)
    out = list(map(lambda x: str(x).title(), out))
    return out


def StringTupleList(ctx, param, value):
    out = value
    if isinstance(value, tuple):
        out = list(value)
    if isinstance(value, str):
        out = [value]
    return out
