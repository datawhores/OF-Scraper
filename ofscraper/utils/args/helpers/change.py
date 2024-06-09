
from ofscraper.utils.args.read import retriveArgs
from ofscraper.utils.args.write import setArgs
def changeargs(newargs):
    args=retriveArgs()
    args = setArgs(args.update(newargs))
    return args