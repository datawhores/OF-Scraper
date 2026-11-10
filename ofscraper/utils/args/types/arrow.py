import re

import arrow
import cloup as click


class ArrowType(click.ParamType):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def convert(self, value, param, ctx):
        out = super().convert(value, param, ctx)
        if not out:
            return out
        try:
            return self._parse(out)
        except ValueError:
            # arrow's ParserError is a ValueError too; report it through click
            # instead of a traceback
            self.fail(
                f"{out!r} isn't a date. Use MM/DD/YYYY, YYYY-MM-DD, "
                "or a relative date such as '3 weeks ago'",
                param,
                ctx,
            )

    def _parse(self, out):
        try:
            t = arrow.get(str(out))
        except arrow.parser.ParserError:
            try:
                # --before/--after document MM/DD/YYYY, which arrow.get() doesn't parse
                t = arrow.get(str(out), ["MM/DD/YYYY", "M/D/YYYY"])
            except arrow.parser.ParserError:
                x = out
                x = re.sub("\\byear\\b", "years", x)
                x = re.sub("\\bday\\b", "days", x)
                x = re.sub("\\bmonth\\b", "months", x)
                x = re.sub("\\bweek\\b", "weeks", x)
                x = re.sub("\\bhour\\b", "hours", x)
                x = re.sub("\\bminute\\b", "minutes", x)
                x = re.sub("\\bsecond\\b", "seconds", x)

                arw = arrow.now()
                t = arw.dehumanize(x)
        return t

    @property
    def name(self):
        return "Arrow"
