import re

from rich.markup import escape


def escape_text(value) -> str:
    """Return ``value`` as text that Rich markup prints exactly as is.

    ``rich.markup.escape`` only protects brackets that look like a tag.
    Rich also turns any ``\\[`` into ``[``, so a Windows path such as
    ``logs\\[2024]`` would lose its backslash; doubling the backslashes
    before those brackets too keeps them.
    """
    return re.sub(r"(\\+)(\[(?![a-z#/@]))", r"\1\\\2", escape(str(value)))
