import arrow
def retry_modifiy(ctx):
     # Modify the URL based on certain conditions or ctx values
    if ctx.params['redownload']:
        ctx.params["force_all"] = True
        ctx.params["after"] = arrow.get(2000)
        ctx.params["no_api_cache"]=True
    return ctx