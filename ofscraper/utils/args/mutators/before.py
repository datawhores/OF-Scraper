import arrow

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args


def update_before():
    args = read_args.retriveArgs()
    if args.before_original:
        return
    args.before = arrow.now().shift(days=4)
    write_args.setArgs(args)
