import logging
import re
from rich.text import Text

# Assumes you have this module for getting sensitive patterns
import ofscraper.utils.logs.utils.sensitive as sensitive


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
        # Fetch the complete, up-to-the-minute dictionary of rules
        sensitive_dict = sensitive.getSenstiveDict()
        for pattern, replacement in sensitive_dict.items():
            s = re.sub(pattern, replacement, s)
        return s

    def format(self, record: logging.LogRecord) -> str:
        # Call the parent's format method first
        original = super().format(record)
        # Then, filter the result
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
        t = re.sub(r"\[.*?\]", "", t)  # Strip any remaining unsupported Rich tags
        t = Text.from_markup(t).plain  # Handle any lingering markup entities
        t = re.sub(r" +", " ", t)  # Consolidate multiple spaces
        t = re.sub(r"\*\*+", "**", t)  # Fix cases like "****"
        t = re.sub(r"__+", "__", t)
        t = re.sub(r"~~+", "~~", t)
        t = t.replace("\\", "")  # Remove escape characters
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
        return Text.from_markup(t).plain
