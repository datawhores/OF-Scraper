import arrow
def retry_modifiy(ctx):
     # Modify the URL based on certain conditions or ctx values
    if ctx.params['redownload']:
        ctx.params["force_all"] = True
        ctx.params["after"] = arrow.get(2000)
        ctx.params["no_api_cache"]=True
    return ctx

# def check_mode_changes(func):
#     @functools.wraps(func)
#     # @click.pass_context
#     def wrapper(ctx, *args, **kwargs):
#         # fix before for check modes
#         ctx.params["before"] = date_helper.before_callback(ctx, ctx.params, None)

#         return func(ctx, *args, **kwargs)

#     return wrapper