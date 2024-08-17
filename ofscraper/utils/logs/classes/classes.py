import logging
import re

from rich.text import Text

import ofscraper.utils.logs.utils.level as level


class DebugOnly(logging.Filter):
    def filter(self, record):
        if record.levelno == 10 or record.levelno == 11:
            return True
        return False


class TraceOnly(logging.Filter):
    def filter(self, record):
        if record.levelno <= 11:
            return True
        return False


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
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        t = SensitiveFormatter._filter(s)
        t = re.sub("\\\\+", "\\\\", t)
        t = re.sub("\[bold[^\]]*]", "**", t)
        t = re.sub("\[\/bold[^\]]*]", "**", t)
        t = Text.from_markup(Text(t).plain).plain
        t = re.sub("  +", " ", t)
        t = re.sub("\*\*+", "**", t)
        t = re.sub("\\\\+", "", t)
        return t


class LogFileFormatter(SensitiveFormatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        t = SensitiveFormatter._filter(s)
        return Text.from_markup(Text(t).plain).plain
