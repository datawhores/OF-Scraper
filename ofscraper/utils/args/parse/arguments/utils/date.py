import arrow


def before_callback(ctx, param, value):
    params = ctx.params
    if not value:
        params[f"{param.name}_original"] = value
        params[f"{param.name}"] = arrow.get(value or arrow.now()).shift(days=4)
        return params[f"{param.name}"]
    else:
        params[f"{param.name}_original"] = value
        params[f"{param.name}"] =value
        return params[f"{param.name}"]
