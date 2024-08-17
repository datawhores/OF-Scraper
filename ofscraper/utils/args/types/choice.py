import re
from gettext import ngettext

import cloup as click


class MultiChoice(click.Choice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def convert(self, value, param, ctx):
        # Match through normalization and case sensitivity MultiChoice
        # first do token_normalize_func, then lowercase
        # preserve original `value` to produce an accurate message in
        # `self.fail`
        if isinstance(value, list):
            return value
        elif not bool(value):
            return []
        values = re.split(",| ", value)
        # dedupe
        seen = set()
        normed_values = [
            normed_value
            for normed_value in values
            if normed_value not in seen and not seen.add(normed_value)
        ]
        normed_choices = [choice for choice in self.choices]

        if ctx is not None and ctx.token_normalize_func is not None:
            for i in range(len(normed_values)):
                normed_values[i] = ctx.token_normalize_func(normed_values[i])
            normed_choices = set(
                [
                    ctx.token_normalize_func(normed_choice)
                    for normed_choice in normed_choices
                ]
            )

        if not self.case_sensitive:
            for i in range(len(normed_values)):
                normed_values[i] = normed_values[i].casefold()
            normed_choices = set(
                [normed_choice.casefold() for normed_choice in normed_choices]
            )

        for normed_value in normed_values:
            if normed_value not in normed_choices:
                choices_str = ", ".join(map(repr, self.choices))
                self.fail(
                    ngettext(
                        "{value!r} is not {choice}.",
                        "{value!r} is not one of {choices}.",
                        len(self.choices),
                    ).format(
                        value=normed_value, choice=choices_str, choices=choices_str
                    ),
                    param,
                    ctx,
                )
        return normed_values


class MultiChoicePost(MultiChoice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def convert(self, value, param, ctx):
        # Match through normalization and case sensitivity MultiChoice
        # first do token_normalize_func, then lowercase
        # preserve original `value` to produce an accurate message in
        # `self.fail`
        if isinstance(value, list):
            return value
        elif not bool(value):
            return []
        values = re.split(",| ", value)
        # dedupe
        seen = set()
        normed_values = [
            normed_value
            for normed_value in values
            if normed_value not in seen and not seen.add(normed_value)
        ]
        normed_choices = [choice for choice in self.choices]

        if ctx is not None and ctx.token_normalize_func is not None:
            for i in range(len(normed_values)):
                normed_values[i] = ctx.token_normalize_func(normed_values[i])
            normed_choices = set(
                [
                    ctx.token_normalize_func(normed_choice)
                    for normed_choice in normed_choices
                ]
            )

        if not self.case_sensitive:
            for i in range(len(normed_values)):
                normed_values[i] = normed_values[i].casefold()
            normed_choices = set(
                [normed_choice.casefold() for normed_choice in normed_choices]
            )

        for normed_value in normed_values:
            if re.sub("^-", "", normed_value, count=1) not in normed_choices:
                choices_str = ", ".join(map(repr, self.choices))
                self.fail(
                    ngettext(
                        "{value!r} is not {choice}.",
                        "{value!r} is not one of {choices}.",
                        len(self.choices),
                    ).format(
                        value=normed_value, choice=choices_str, choices=choices_str
                    ),
                    param,
                    ctx,
                )
        return normed_values


class MutuallyExclusiveMultichoice(MultiChoice):
    def __init__(self, *args, exclusion=None, **kwargs):
        self._exclusion = exclusion or []
        super().__init__(*args, **kwargs)

    def convert(self, value, param, ctx):
        out = super().convert(value, param, ctx)
        if not out:
            return out
        for val in self._exclusion_helper():
            if all([ele in out for ele in val]):
                self.fail(f"The values {','.join(val)} can not be together")
        return out

    def _exclusion_helper(self):
        if len(self._exclusion) == 0:
            return self._exclusion
        if not isinstance(self._exclusion[0], list):
            return [self._exclusion]
