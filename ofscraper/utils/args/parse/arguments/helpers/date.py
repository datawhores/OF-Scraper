import arrow

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args



def before_callback(ctx, param, value):
    params = ctx.params
    params["before_original"] = value
    params["before"] = arrow.get(value or arrow.now()).shift(days=4)
    return params["before"]
