import itertools
def MultiChoiceCallback(ctx, param, value):
    out= (
        list(map(lambda x:x.capitalize(),list(set(itertools.chain.from_iterable(value))) if value else []
    ))) 
    seen = set()
    return [value for value in out if value not in seen and not seen.add(value)]
