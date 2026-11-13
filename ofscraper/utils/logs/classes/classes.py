import logging
import re
from rich.errors import MarkupError
from rich.logging import RichHandler
from rich.text import Text

# Assumes you have this module for getting sensitive patterns
import ofscraper.utils.logs.utils.sensitive as sensitive


def _unescape(t: str) -> str:
    # What Rich would have done with "\[" escapes
    return re.sub(r"\\(\[)", r"\1", t)


def strip_markup(t: str) -> str:
    """Plain text of a Rich-markup string; the text as is (escapes removed) if
    the markup is broken (e.g. a stray closing tag), so the line is still
    logged."""
    try:
        return Text.from_markup(t).plain
    except MarkupError:
        return _unescape(t)


class SafeRichHandler(RichHandler):
    """RichHandler that prints a line with broken markup as plain text instead
    of dropping it."""

    def render_message(self, record, message):
        try:
            return super().render_message(record, message)
        except MarkupError:
            return Text(_unescape(message))


class TraceBackOnly(logging.Filter):
    """A filter to only allow log records with a specific traceback level."""

    def filter(self, record):
        return record.levelno == 11


class NoTraceBack(logging.Filter):
    """A filter to exclude log records with a specific traceback level."""

    def filter(self, record):
        return record.levelno != 11


class NoDebug(logging.Filter):
    """A filter to exclude log records at or below the debug level."""

    def filter(self, record):
        return record.levelno > 11


class SensitiveFormatter(logging.Formatter):
    """
    Base formatter that dynamically removes sensitive information in logs
    by fetching all patterns from the 'sensitive' module at runtime.
    """

    def _filter(self, s: str) -> str:
        # Fetch the rules
        sensitive_dict = sensitive.getSenstiveDict()
        for pattern, replacement in sensitive_dict.items():
            try:
                # Try to replace the pattern
                s = re.sub(pattern, replacement, s)
            except re.error:
                # DO NOT use sys.stderr here if you are worried about Rich.
                # Instead, modify 's' to include the warning.
                # This ensures Rich prints it safely as part of the log line.
                s += f"\n [LOGGING ERROR: Bad regex pattern '{pattern}']"
        return s

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return self._filter(original)


class DiscordFormatter(SensitiveFormatter):
    """
    Formatter that converts rich markup and removes sensitive information
    for safe display in Discord.
    """

    def _filter(self, s: str) -> str:  # Added 'self'
        # First, apply the parent's sensitive data filtering
        t = super()._filter(s)

        # --- Convert Rich-style tags to Discord Markdown ---
        t = re.sub(
            r"\[bold[^\]]*](.*?)\[/bold[^\]]*]", r"**\1**", t, flags=re.IGNORECASE
        )
        t = re.sub(
            r"\[italic[^\]]*](.*?)\[/italic[^\]]*]", r"*\1*", t, flags=re.IGNORECASE
        )
        t = re.sub(
            r"\[underline[^\]]*](.*?)\[/underline[^\]]*]",
            r"__\1__",
            t,
            flags=re.IGNORECASE,
        )
        t = re.sub(
            r"\[strike[^\]]*](.*?)\[/strike[^\]]*]", r"~~\1~~", t, flags=re.IGNORECASE
        )
        t = re.sub(r"\[code[^\]]*](.*?)\[/code[^\]]*]", r"`\1`", t, flags=re.IGNORECASE)

        # --- Cleanup and Final Touches ---
        t = strip_markup(t)  # Handle any lingering markup entities
        t = re.sub(r" +", " ", t)  # Consolidate multiple spaces
        t = re.sub(r"\*\*+", "**", t)  # Fix cases like "****"
        t = re.sub(r"__+", "__", t)
        t = re.sub(r"~~+", "~~", t)
        # Remove escape characters
        t = re.sub(r"\\([\[\]])", r"\1", t)
        return t.strip()


class LogFileFormatter(SensitiveFormatter):
    """
    Formatter that strips all rich markup for clean log files,
    after redacting sensitive information.
    """

    def _filter(self, s: str) -> str:  # Added 'self'
        # First, apply the parent's sensitive data filtering
        t = super()._filter(s)
        # Then, strip all rich markup for a plain text representation
        return strip_markup(t)
