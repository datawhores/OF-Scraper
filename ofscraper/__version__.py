from __future__ import annotations
import importlib.metadata

# The version is now read from the installed package's metadata.
# The distribution is published as 'ofscraper-community' and, from
# datawhores/OF-Scraper, as 'ofscraper'; the import package and the command are
# 'ofscraper' either way. __dist_name__ is the one installed, so the update
# check and install hints name the PyPI project the user installed from. Keep
# the names literal: PyInstaller looks for them to bundle the metadata into the
# binaries.
try:
    __version__ = importlib.metadata.version("ofscraper-community")
    __dist_name__ = "ofscraper-community"
except importlib.metadata.PackageNotFoundError:
    try:
        __version__ = importlib.metadata.version("ofscraper")
        __dist_name__ = "ofscraper"
    except importlib.metadata.PackageNotFoundError:
        # This is a fallback for cases where the package is not installed at all,
        # or you are in a situation where metadata is not available.
        __version__ = "0.0.0" # A sensible fallback
        __dist_name__ = "ofscraper-community"
