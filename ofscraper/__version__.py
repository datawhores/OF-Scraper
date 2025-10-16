from __future__ import annotations
import importlib.metadata

# The version is now read from the installed package's metadata
try:
    # This will read the version from the installed package's metadata.
    # __name__ is the name of your package (e.g., 'ofscraper')
    __version__ =   importlib.metadata.version("ofscraper")
except importlib.metadata.PackageNotFoundError:
    # This is a fallback for cases where the package is not installed at all,
    # or you are in a situation where metadata is not available.
    __version__ = "0.0.0" # A sensible fallback