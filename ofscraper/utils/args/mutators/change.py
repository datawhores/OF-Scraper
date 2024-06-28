from ofscraper.utils.args.accessors.read import retriveArgs
from ofscraper.utils.args.mutators.write import setArgs


def changeargs(newargs):
    args = retriveArgs()
    args = setArgs(args.update(newargs))
    return args
