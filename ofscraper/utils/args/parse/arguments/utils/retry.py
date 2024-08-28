import arrow
def retry_callback(ctx, param, value):
    params = ctx.params
    if value:
        params["force_all"] = True
        params["after"] = arrow.get(2000)
        params["no_api_cache"]=True