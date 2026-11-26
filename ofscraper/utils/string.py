import os
import re
import string

###
# https://github.com/pypa/cibuildwheel/issues/840
# This alternative implementation allows for bad values to be ignored by using regex instead
###


def format_safe(template: str, **kwargs: str | os.PathLike[str]) -> str:
    r"""
    Works similarly to `template.format(**kwargs)`, except that unmatched
    fields in `template` are passed through untouched.

    >>> format_safe('{a} {b}', a='123')
    '123 {b}'
    >>> format_safe('{a} {b[4]:3f}', a='123')
    '123 {b[4]:3f}'

    To avoid variable expansion, precede with a single backslash e.g.
    >>> format_safe('\\{a} {b}', a='123')
    '{a} {b}'
    """

    result = template

    for key, value in kwargs.items():
        find_pattern = re.compile(
            rf"""
                (?<!\#)  # don't match if preceded by a hash
                {{  # literal open curly bracket
                {re.escape(key)}  # the field name
                }}  # literal close curly bracket
            """,
            re.VERBOSE,
        )

        result = re.sub(
            pattern=find_pattern,
            repl=str(value).replace("\\", r"\\"),
            string=result,
        )

        # transform escaped sequences into their literal equivalents
        result = result.replace(f"#{{{key}}}", f"{{{key}}}")

    return result


def parse_safe(value):
    file_format = set()
    iter_parse = iter(string.Formatter().parse(value))
    while True:
        try:
            text, name, spec, conv = next(iter_parse)
            file_format.add(name)
        except ValueError:
            continue
        except StopIteration:
            break
    return file_format


_BLOCK = r"(?:p|div|li|h[1-6])\b"


def html_lines(text):
    """An HTML caption's text with its line breaks: a <br>, and the start or
    end of a paragraph, div, list item or heading, is a line break, and the
    other tags are removed. The start of a block that begins a line already
    adds no empty line. Entities are left encoded."""
    text = re.sub(rf"<br\s*/?>|</{_BLOCK}[^>]*>", "\n", text, flags=re.I)
    # tags that aren't a block's start go first, so "</b><ul><li>" is
    # read as the start of a line
    text = re.sub(rf"<(?!{_BLOCK})[^>]*>", "", text, flags=re.I)
    text = re.sub(rf"(?<=[^\s])([ \t]*)<{_BLOCK}[^>]*>", "\\1\n", text, flags=re.I)
    return re.sub(r"<[^>]*>", "", text)
