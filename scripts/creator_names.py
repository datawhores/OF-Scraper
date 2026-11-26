"""Compatibility wrapper for ``ofscraper creator_names``."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ofscraper.commands.creator_names import main

if __name__ == "__main__":
    sys.exit(main())
