import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args

import arrow
def update_before():
    args=read_args.retriveArgs()
    if args.before_original:
        return
    args.before=arrow.now().shift(days=4)
    write_args.setArgs(args)