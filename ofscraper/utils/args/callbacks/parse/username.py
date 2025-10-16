from ofscraper.utils.args.callbacks.parse.string import StringSplitParse

def UsernameParse(ctx, param, value):
    out = StringSplitParse(ctx, param, value)
    out = list(map(lambda y: y.lower() if not y == "ALL" else y, out))
    return out