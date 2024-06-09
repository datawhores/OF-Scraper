import arrow

import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args


def update_before():
    args = read_args.retriveArgs()
    if args.before_original:
        return
    args.before = arrow.now().shift(days=4)
    write_args.setArgs(args)


def before_callback(ctx, param, value):
    params = ctx.params
    params["before_original"] = value
    params["before"] = arrow.get(value or arrow.now()).shift(days=4)
    return params["before"]
