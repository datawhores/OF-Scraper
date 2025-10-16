import itertools
import re


def MultiChoiceCallback(ctx, param, value):
    # out=map(lambda x:[x] if not isinstance(x,list) else value,value)
    out = value
    out = list(set(itertools.chain.from_iterable(out))) if out else []
    seen = set()
    return [value for value in out if value not in seen and not seen.add(value)]


def choiceClean(ctx, param, value):
    return list(map(lambda x: re.sub(r"[^a-zA-Z\*\+]", "", str.title(x)), value))
