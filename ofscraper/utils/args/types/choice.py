import cloup as click
import re
from gettext import ngettext
class MultiChoice(click.Choice):
    def __init__(self,args,**kwargs):
        super().__init__(args,**kwargs)
    def convert(
        self, value, param, ctx 
    ):
        # Match through normalization and case sensitivity MultiChoice
        # first do token_normalize_func, then lowercase
        # preserve original `value` to produce an accurate message in
        # `self.fail`
        normed_values=re.split(",| ", value)  
        normed_choices = [choice for choice in self.choices]

        if ctx is not None and ctx.token_normalize_func is not None:
            for i in range(len(normed_value)):
                normed_values[i]=ctx.token_normalize_func(normed_values[i])
            normed_choices = set([ctx.token_normalize_func(normed_choice) for normed_choice in normed_choices])

        if not self.case_sensitive:
            for i in range(len(normed_values)):
                normed_values[i]=normed_values[i].casefold()
            normed_choices = set([normed_choice.casefold() for normed_choice in normed_choices])

        for normed_value in normed_values:
            if not normed_value in normed_choices:
                choices_str = ", ".join(map(repr, self.choices))
                self.fail(
                    ngettext(
                        "{value!r} is not {choice}.",
                        "{value!r} is not one of {choices}.",
                        len(self.choices),
                    ).format(value=normed_value, choice=choices_str, choices=choices_str),
                    param,
                    ctx,
                )                                                   
        return normed_values
