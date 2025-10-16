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
            t = arrow.get(out)
        except arrow.parser.ParserError:
            try:
                x = out
                x = re.sub("\\byear\\b", "years", x)
                x = re.sub("\\bday\\b", "days", x)
                x = re.sub("\\bmonth\\b", "months", x)
                x = re.sub("\\bweek\\b", "weeks", x)
                arw = arrow.utcnow()
                t = arw.dehumanize(x)
            except ValueError as E:
                raise E
        return t

    @property
    def name(self):
        return "Arrow"
