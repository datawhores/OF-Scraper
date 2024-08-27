import arrow


def before_callback(ctx, param, value):
    params = ctx.params
    if not value:
        params["before_original"] = value
        params["before"] = arrow.get(value or arrow.now()).shift(days=4)
        return params["before"]
    else:
        params["before_original"] = value
        params["before"] =value
        return params["before"]
