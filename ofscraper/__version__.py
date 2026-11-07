from __future__ import annotations
import importlib.metadata

# The version is now read from the installed package's metadata
try:
    # The distribution is published as 'ofscraper-community'; the import
    # package and the command are still 'ofscraper'. Keep the name a literal:
    # PyInstaller looks for it to bundle the metadata into the binaries.
    __version__ = importlib.metadata.version("ofscraper-community")
except importlib.metadata.PackageNotFoundError:
    # This is a fallback for cases where the package is not installed at all,
    # or you are in a situation where metadata is not available.
    __version__ = "0.0.0" # A sensible fallback
