import itertools
def MultiChoiceCallback(ctx, param, value):
    return (
        list(map(lambda x:x.capitalize(),list(set(itertools.chain.from_iterable(value))) if value else []
    ))) 