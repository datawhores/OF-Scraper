import re

import cloup as click
from click import BadParameter

from ofscraper.utils.args.parse.group_bundles.db import db_args

def parse_ids(value, option):
    """The whole ids in an option's value, as ints: one id, or several split
    by commas or spaces as the main command's --post-id takes them (#363).
    The database stores ids as numbers, so they're compared as numbers. A
    value with no id in it is an error, not "no filter": with
    --unmark-permanent-skips that would un-mark every row."""
    ids = set()
    for part in re.split(r"[,\s]+", str(value).strip()):
        if not part:
            continue
        # isdecimal: exactly the digits int() reads, from any script
        # ("١٢٣" is 123). isdigit() also takes "²", which int() can't read
        if not part.isdecimal():
            raise BadParameter(f"{part!r} is not an id", param_hint=option)
        try:
            ids.add(int(part))
        except ValueError:
            # longer than int()'s digit limit (sys.get_int_max_str_digits)
            raise BadParameter(
                f"{part[:20]!r}... is not an id", param_hint=option
            ) from None
    if not ids:
        raise BadParameter("no id given", param_hint=option)
    return ids


@db_args
@click.pass_context
def db(ctx, *args, **kwargs):
    # None: the option wasn't given. Any value given, even an empty one, is
    # parsed
    if ctx.params["post_id"] is not None:
        ctx.params["post_id"] = parse_ids(ctx.params["post_id"], "--post-id")
    if ctx.params["media_id"] is not None:
        ctx.params["media_id"] = parse_ids(ctx.params["media_id"], "--media-id")
    return ctx.params, ctx.info_name
