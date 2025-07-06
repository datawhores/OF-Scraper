import logging
import re

from rich.text import Text

import ofscraper.utils.logs.utils.level as level


class TraceBackOnly(logging.Filter):
    def filter(self, record):
        if record.levelno == 11:
            return True
        return False


class NoTraceBack(logging.Filter):
    def filter(self, record):
        if record.levelno != 11:
            return True
        return False


class NoDebug(logging.Filter):
    def filter(self, record):
        if record.levelno <= 11:
            return False
        return True


class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        t = re.sub("&Policy=[^&\"']+", "&Policy={hidden}", s)
        t = re.sub("&Signature=[^&\"']+", "&Signature={hidden}", t)
        t = re.sub("&Key-Pair-Id=[^&\"']+", "&Key-Pair-Id={hidden}", t)
        for ele in level.getSenstiveDict().items():
            t = re.sub(re.escape(str(ele[0])), str(ele[1]), t)
        return t

    def format(self, record):
        original = logging.Formatter.format(self, record)  # call parent method
        return self._filter(original)


class DiscordFormatter(SensitiveFormatter):
    """
    Formatter that converts rich markup and removes sensitive information
    for safe display in Discord.
    """

    @staticmethod
    def _filter(s: str) -> str:
        # First, apply the parent's sensitive data filtering
        t = SensitiveFormatter._filter(s)

        # --- Convert Rich-style tags to Discord Markdown ---
        # Bold
        t = re.sub(r"\[bold[^\]]*](.*?)\[/bold[^\]]*]", r"**\1**", t, flags=re.IGNORECASE)
        # Italic
        t = re.sub(r"\[italic[^\]]*](.*?)\[/italic[^\]]*]", r"*\1*", t, flags=re.IGNORECASE)
        # Underline
        t = re.sub(r"\[underline[^\]]*](.*?)\[/underline[^\]]*]", r"__\1__", t, flags=re.IGNORECASE)
        # Strikethrough
        t = re.sub(r"\[strike[^\]]*](.*?)\[/strike[^\]]*]", r"~~\1~~", t, flags=re_IGNORECASE)
        # Inline code
        t = re.sub(r"\[code[^\]]*](.*?)\[/code[^\]]*]", r"`\1`", t, flags=re.IGNORECASE)

        # --- Cleanup and Final Touches ---
        # Strip any remaining or unsupported Rich tags (e.g., [red], [link])
        # This leaves the content inside the tags intact.
        t = re.sub(r"\[.*?\]", "", t)

        # Use Rich's Text class to handle any lingering markup entities
        t = Text.from_markup(t).plain

        # Consolidate multiple spaces and fix markdown artifacts
        t = re.sub(r" +", " ", t)
        t = re.sub(r"\*\*+", "**", t) # Fix cases like "****"
        t = re.sub(r"__+", "__", t)
        t = re.sub(r"~~+", "~~", t)

        # Remove backslashes used for escaping in the original markup
        t = t.replace("\\", "")

        return t.strip()

class LogFileFormatter(SensitiveFormatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        t = SensitiveFormatter._filter(s)
        return Text.from_markup(Text(t).plain).plain
