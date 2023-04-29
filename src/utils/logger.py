import logging
import src.utils.args as args_
import src.utils.paths as paths
import re

class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        # Filter out the password with regex
        # or replace etc.
        # Replace here with your own regex..
        s=re.sub("&Policy=[^&]+", "&Policy={hidden}", s)
        s=re.sub("&Signature=[^&]+", "&Signature={hidden}", s)
        s=re.sub("&Key-Pair-Id=[^&]+", "&Key-Pair-Id={hidden}", s)
        return s

    def format(self, record):
        original = logging.Formatter.format(self, record)  # call parent method
        return self._filter(original)
log=logging.getLogger("ofscraper")
log.setLevel(args_.getargs().log or 100)
fh=logging.FileHandler(paths.getlogpath(),mode="a")
fh.setLevel(args_.getargs().log or 100)
formatter = SensitiveFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',"%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
log.addHandler(fh)
